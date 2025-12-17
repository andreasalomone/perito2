"""
Assicurati API endpoints.

Simple CRUD for insured parties (assicurati).
Unlike Clients, no LLM enrichment is triggered.
"""

import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_token, get_db
from app.models import Assicurato, User
from app.schemas.assicurato import AssicuratoListItem

logger = logging.getLogger("app.api.assicurati")

router = APIRouter()


@router.get(
    "/",
    response_model=List[AssicuratoListItem],
    summary="List/Search Assicurati",
    description="Search for assicurati (insured parties) within the current user's organization.",
)
def list_assicurati(
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(
        None,
        description="Search query for assicurato name (optional, returns all if empty)",
    ),
    limit: int = 10,
    skip: int = 0,
) -> List[AssicuratoListItem]:
    """
    Returns a list of assicurati matching the search query.
    Restricted to the current user's organization.
    Used by the AssicuratoCombobox component for autocomplete.
    """
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    org_id = user.organization_id

    stmt = (
        select(Assicurato.id, Assicurato.name)
        .where(Assicurato.organization_id == org_id)
    )

    if q:
        # Escape LIKE wildcards to prevent injection
        safe_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Assicurato.name.ilike(f"%{safe_q}%", escape="\\"))

    # Order by name, with limit/skip
    stmt = stmt.order_by(Assicurato.name.asc()).offset(skip).limit(limit)

    results = db.execute(stmt).all()

    return [
        AssicuratoListItem(id=row.id, name=row.name)
        for row in results
    ]

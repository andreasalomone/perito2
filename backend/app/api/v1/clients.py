import logging
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_token, get_db
from app.models import Client, User
from app import schemas
from pydantic import BaseModel

logger = logging.getLogger("app.api.clients")

router = APIRouter()

class ClientSimple(BaseModel):
    id: UUID
    name: str
    
    class Config:
        from_attributes = True

@router.get(
    "/",
    response_model=List[ClientSimple],
    summary="Search Clients",
    description="Search for clients within the current user's organization."
)
def search_clients(
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(None, min_length=1, description="Search query for client name"),
    limit: int = 10
) -> List[Client]:
    """
    Returns a list of clients matching the search query.
    Restricted to the current user's organization via RLS/User lookup.
    """
    # 1. Get Organization ID from User (Source of Truth)
    user = db.get(User, current_user["uid"])
    if not user:
        # Should be covered by dependency, but good for safety
        return []

    org_id = user.organization_id
    
    stmt = select(Client).where(Client.organization_id == org_id)
    
    if q:
        # Case-insensitive search using ILIKE
        stmt = stmt.where(Client.name.ilike(f"%{q}%"))
    
    stmt = stmt.order_by(Client.name.asc()).limit(limit)
    
    return list(db.scalars(stmt).all())

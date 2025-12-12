import logging
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_token, get_db
from app.models import Client, User
from app.schemas.client import ClientCreate, ClientDetail, ClientListItem, ClientUpdate
from app.services.case_service import trigger_client_enrichment_task
from app.services.enrichment_service import EnrichedClientData, EnrichmentService

logger = logging.getLogger("app.api.clients")

router = APIRouter()


class EnrichmentRequest(BaseModel):
    query_name: str


@router.get(
    "/",
    response_model=List[ClientListItem],
    summary="List/Search Clients",
    description="Search for clients within the current user's organization.",
)
def list_clients(
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(
        None,
        description="Search query for client name (optional, returns all if empty)",
    ),
    limit: int = 50,
    skip: int = 0,
) -> List[ClientListItem]:
    """
    Returns a list of clients matching the search query.
    Restricted to the current user's organization.
    """
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    org_id = user.organization_id

    from sqlalchemy import func

    from app.models import Case

    # Join with Case to count cases per client
    # Outer join to include clients with 0 cases
    stmt = (
        select(
            Client.id,
            Client.name,
            Client.logo_url,
            Client.city,
            func.count(Case.id).label("case_count"),
        )
        .outerjoin(Case, (Case.client_id == Client.id) & (Case.deleted_at.is_(None)))
        .where(Client.organization_id == org_id)
    )

    if q:
        stmt = stmt.where(Client.name.ilike(f"%{q}%"))

    stmt = stmt.group_by(Client.id)

    # Order by name, with limit/skip
    # Can also order by count if needed in future
    stmt = stmt.order_by(Client.name.asc()).offset(skip).limit(limit)

    results = db.execute(stmt).all()

    # Map raw rows to ClientListItem
    return [
        ClientListItem(
            id=row.id,
            name=row.name,
            logo_url=row.logo_url,
            city=row.city,
            case_count=row.case_count,
        )
        for row in results
    ]


@router.post(
    "/",
    response_model=ClientDetail,
    summary="Create Client",
    description="Create a new client manually.",
)
def create_client(
    client_in: ClientCreate,
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    # Check if client already exists (UniqueConstraint)
    existing = (
        db.query(Client)
        .filter(
            Client.organization_id == user.organization_id,
            Client.name == client_in.name,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409, detail=f"Client '{client_in.name}' already exists."
        )

    try:
        new_client = Client(
            organization_id=user.organization_id, **client_in.model_dump()
        )
        db.add(new_client)
        db.commit()
        db.refresh(new_client)

        # Trigger enrichment for the new client
        trigger_client_enrichment_task(str(new_client.id), new_client.name)

        return new_client

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Client already exists") from None
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create client") from e


@router.get(
    "/{client_id}",
    response_model=ClientDetail,
    summary="Get Client Details",
)
def get_client(
    client_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    client = db.get(Client, client_id)
    if not client or client.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Client not found")

    return client


@router.patch(
    "/{client_id}",
    response_model=ClientDetail,
    summary="Update Client",
)
def update_client(
    client_id: UUID,
    client_in: ClientUpdate,
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    client = db.get(Client, client_id)
    if not client or client.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Client not found")

    # Set RLS context for safety (though ORM check above is good)
    db.execute(
        text("SELECT set_config('app.current_org_id', :oid, false)"),
        {"oid": str(user.organization_id)},
    )

    update_data = client_in.model_dump(exclude_unset=True)

    # If name is being updated, check uniqueness
    if "name" in update_data and update_data["name"] != client.name:
        existing = (
            db.query(Client)
            .filter(
                Client.organization_id == user.organization_id,
                Client.name == update_data["name"],
                Client.id != client_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Client '{update_data['name']}' already exists.",
            )

    for field, value in update_data.items():
        setattr(client, field, value)

    try:
        db.commit()
        db.refresh(client)
        return client
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Update causes conflict") from None
    except Exception as e:
        logger.error(f"Error updating client {client_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update client") from e


@router.post(
    "/{client_id}/enrich",
    summary="Trigger Enrichment",
    description="Manually trigger the AI enrichment process for a client.",
)
def trigger_enrichment(
    client_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    client = db.get(Client, client_id)
    if not client or client.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Client not found")

    # Trigger async task
    trigger_client_enrichment_task(str(client.id), client.name)

    return {"message": "Enrichment task started"}


@router.post(
    "/enrich",
    response_model=Optional[EnrichedClientData],
    summary="Stateless Enrichment Preview",
    description="Fetch company data from Gemini without saving to DB (Preview).",
)
async def enrich_preview(
    request: EnrichmentRequest,
    current_user: Annotated[dict, Depends(get_current_user_token)],
):
    """
    Stateless lookup for frontend preview.
    Does NOT require DB write access, but authorized user is required.
    """
    service = EnrichmentService()

    # Call service directly (awaitable)
    result = await service.enrich_client(request.query_name)

    if not result:
        return None

    return EnrichedClientData(**result)

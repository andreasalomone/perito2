"""
Client Matcher Service

Fuzzy matching for existing clients using Levenshtein distance.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row: list[int] = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings.
    Returns value between 0.0 (no match) and 1.0 (exact match).
    """
    if not s1 or not s2:
        return 0.0

    # Normalize: lowercase, strip whitespace
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()

    if s1 == s2:
        return 1.0

    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))

    return 1.0 - (distance / max_len)


def fuzzy_match_client(
    db: Session, org_id: UUID, client_name: Optional[str], threshold: float = 0.65
) -> Optional[Client]:
    """
    Find best matching client by name using fuzzy matching.

    Args:
        db: Database session
        org_id: Organization ID for RLS
        client_name: Name to match (e.g., "generali")
        threshold: Minimum similarity ratio (default 0.65 = 65%)

    Returns:
        Best matching Client if similarity > threshold, else None

    Examples:
        "generali" matches "Generali SPA" at ~0.67
        "axa" matches "AXA Assicurazioni" at ~0.75
    """
    if not client_name:
        return None

    # Get all clients for this organization
    result = db.execute(select(Client).where(Client.organization_id == org_id))
    clients = result.scalars().all()

    if not clients:
        return None

    # Find best match
    best_match: Optional[Client] = None
    best_score: float = 0.0

    for client in clients:
        score = similarity_ratio(client_name, client.name)
        if score > best_score:
            best_score = score
            best_match = client

    if best_score >= threshold and best_match is not None:
        logger.info(
            f"Fuzzy matched '{client_name}' -> '{best_match.name}' (score: {best_score:.2f})"
        )
        return best_match

    logger.info(
        f"No fuzzy match for '{client_name}' (best score: {best_score:.2f} < {threshold})"
    )
    return None


def find_or_create_client(
    db: Session, org_id: UUID, client_name: Optional[str], threshold: float = 0.65
) -> Optional[Client]:
    """
    Find existing client by fuzzy match, or create new one.

    Args:
        db: Database session
        org_id: Organization ID
        client_name: Client name from AI extraction
        threshold: Fuzzy match threshold

    Returns:
        Matched or newly created Client, or None if no name provided
    """
    if not client_name:
        return None

    # Try fuzzy match first
    existing = fuzzy_match_client(db, org_id, client_name, threshold)
    if existing:
        return existing

    # Create new client
    new_client = Client(organization_id=org_id, name=client_name.strip())
    db.add(new_client)
    db.flush()

    logger.info(f"Created new client: '{new_client.name}' (id: {new_client.id})")
    return new_client

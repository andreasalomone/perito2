import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("app.security")

@contextmanager
def secure_session(db: Session, user_id: str, org_id: str):
    """
    Wraps a DB session to enforce RLS context setting and CLEANUP.
    Guarantees no data leakage across pooled connections.
    
    Usage:
        with secure_session(db, user_uid, organization_id):
            # All queries within this block have RLS context set
            result = db.query(Case).all()
        # Context is automatically cleaned up after the block
    
    Args:
        db: SQLAlchemy session
        user_id: Firebase user UID
        org_id: Organization UUID string
    
    Raises:
        HTTPException: If setting or resetting RLS context fails
    """
    try:
        # 1. Set RLS Context Variables
        db.execute(
            text("SELECT set_config('app.current_user_uid', :uid, false), "
                 "set_config('app.current_org_id', :org, false)"),
            {"uid": user_id, "org": org_id}
        )
        logger.debug(f"RLS context set: user={user_id}, org={org_id}")
        yield db
    finally:
        # 2. MANDATORY CLEANUP (Reset to NULL)
        # This protects against connection pooling leaking state to the next request
        try:
            db.execute(text("RESET app.current_user_uid; RESET app.current_org_id;"))
            logger.debug("RLS context reset successfully")
        except Exception as e:
            logger.critical(f"FAILED TO RESET RLS CONTEXT: {e}")
            # If we can't reset, we should invalidate this connection so it's not reused
            # This ensures no data leakage even if reset fails
            db.invalidate()
            logger.warning(f"Connection invalidated due to RLS reset failure")

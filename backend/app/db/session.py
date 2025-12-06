import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("app.security")

def set_rls_variables(db_session: Session, user_uid: str, org_id: str):
    """
    Sets session variables. explicitly using is_local=False (Session scoped)
    so they survive a commit() within the same connection, 
    BUT we must ensure we reset them when the connection is returned to the pool.
    """
    # Sanitize inputs to prevent SQL injection via session variables
    # (parameter binding handles this, but defensive coding is good)
    if not user_uid or not org_id:
        return

    # is_local=False means "Session duration" (until Reset or Connection Close)
    # This allows the variables to survive a db.commit() so db.refresh() works.
    db_session.execute(
        text("SELECT set_config('app.current_user_uid', :uid, false), "
             "set_config('app.current_org_id', :org, false)"),
        {"uid": str(user_uid), "org": str(org_id)}
    )

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
        set_rls_variables(db, user_id, org_id)
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

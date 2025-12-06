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



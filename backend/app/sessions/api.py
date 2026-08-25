# app/sessions/api.py
#
# One endpoint: lets the frontend proactively delete a session's data the
# moment a user explicitly leaves it (see ChatScreen.jsx's exit-confirm
# modal), rather than waiting for the TTL sweep in store.py's
# cleanup_expired_sessions() to eventually catch it. Both paths call the
# same delete_session() -- this is just the fast, deliberate trigger;
# the TTL sweep is the safety net for sessions nobody explicitly closed.

import logging

from fastapi import APIRouter

from app.sessions.store import delete_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete("/session/{session_id}")
def end_session(session_id: str):
    # Deliberately doesn't 404 on a missing/already-deleted session --
    # from the frontend's point of view "make sure this session's data is
    # gone" already succeeded if there was nothing to delete. Erroring
    # here would just be something the frontend has to special-case for
    # no real benefit.
    delete_session(session_id)
    return {"session_id": session_id, "deleted": True}
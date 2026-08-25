# sessions/store.py
#
# Replaces v1's per-session SQLite file. Since v2's analysis engine
# (analysis/registry.py) works directly on pandas dataframes rather than
# SQL tables, there's no reason to round-trip through SQLite anymore --
# we just persist the dataframe itself between requests.
#
# Stored as Parquet (via pyarrow) in storage/sessions/{session_id}.parquet
# -- chosen over pickle because it preserves dtypes safely without being
# a code-execution risk on load, and over CSV because it preserves dtypes
# at all (CSV round-trips would lose datetime/int type info).
#
# NOTE: this currently supports ONE active dataframe per session, not
# multiple named tables like v1's SQLite approach did. If a user selects
# multiple sheets, see api/upload.py for how they're combined -- for now,
# multi-sheet analysis across separate tables isn't supported by the
# planner/analysis engine yet (groupby_agg etc. all take a single df).
#
# CLEANUP: nothing here runs on a schedule -- there's no background worker
# process in this deployment. cleanup_expired_sessions() is instead called
# opportunistically from /upload/inspect (see upload.py) via a FastAPI
# BackgroundTask, so storage gets swept every time someone starts a new
# session rather than needing a separate cron/scheduler to keep running.
# There's also DELETE /session/{session_id} (sessions/api.py) for the
# frontend to call immediately when a user explicitly leaves -- that's the
# fast path; this TTL sweep is the safety net for sessions nobody ever
# explicitly closed (browser closed, tab crashed, upload started and
# abandoned before confirming).

import time
import shutil
from pathlib import Path
import pandas as pd

from app.config import settings

SESSIONS_DIR = Path(settings.storage_dir) / "sessions"
UPLOADS_DIR = Path(settings.storage_dir) / "uploads"


def save_session_df(session_id: str, df: pd.DataFrame) -> None:
    """Persists the working dataframe for a session, overwriting any previous one."""
    path = SESSIONS_DIR / f"{session_id}.parquet"
    df.to_parquet(path, index=False)


def load_session_df(session_id: str) -> pd.DataFrame:
    """
    Loads the working dataframe for a session.
    Raises FileNotFoundError if no session data exists -- the API route
    should catch this and return a 404 telling the user to re-upload.
    """
    path = SESSIONS_DIR / f"{session_id}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No session data found for session_id '{session_id}'")
    return pd.read_parquet(path)


def delete_session(session_id: str) -> None:
    """
    Removes all stored data for a session: the working dataframe, and (as
    a defensive extra -- normally already gone by the time confirm_upload()
    finishes, see upload.py) any leftover raw-upload directory. Safe to
    call even if none of it exists, e.g. the session already expired or
    was already cleaned up.
    """
    parquet_path = SESSIONS_DIR / f"{session_id}.parquet"
    parquet_path.unlink(missing_ok=True)

    upload_dir = UPLOADS_DIR / session_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)


def cleanup_expired_sessions(ttl_hours: float | None = None) -> int:
    """
    Deletes session data (parquet files, plus any orphaned raw-upload
    directories) older than the TTL. Two independent things get swept,
    since either can exist without the other:

      - storage/sessions/*.parquet   -- confirmed sessions nobody's used
        in a while.
      - storage/uploads/{session_id} -- uploads that were inspected (or
        even previewed) but never confirmed, so no parquet file was ever
        created for them and they'd otherwise sit there forever.

    Returns the number of items removed, purely so the caller can log it.
    Never raises -- a failed cleanup sweep shouldn't take down the
    request that triggered it (see upload.py, called as a BackgroundTask).
    """
    if ttl_hours is None:
        ttl_hours = settings.session_ttl_hours
    cutoff = time.time() - (ttl_hours * 3600)

    removed = 0

    if SESSIONS_DIR.exists():
        for parquet_path in SESSIONS_DIR.glob("*.parquet"):
            try:
                if parquet_path.stat().st_mtime < cutoff:
                    delete_session(parquet_path.stem)
                    removed += 1
            except OSError:
                continue

    if UPLOADS_DIR.exists():
        for session_dir in UPLOADS_DIR.iterdir():
            try:
                if session_dir.is_dir() and session_dir.stat().st_mtime < cutoff:
                    shutil.rmtree(session_dir, ignore_errors=True)
                    removed += 1
            except OSError:
                continue

    return removed
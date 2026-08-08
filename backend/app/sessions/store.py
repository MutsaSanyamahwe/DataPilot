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

from pathlib import Path
import pandas as pd

from app.config import settings

SESSIONS_DIR = Path(settings.storage_dir) / "sessions"


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
    """Removes a session's stored dataframe, if it exists. Safe to call even if it doesn't."""
    path = SESSIONS_DIR / f"{session_id}.parquet"
    path.unlink(missing_ok=True)
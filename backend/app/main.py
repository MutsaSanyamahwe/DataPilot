import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.upload import router as upload_router
from app.ask import router as ask_router
from app.suggestions.api import router as suggestions_router
from app.sessions.api import router as sessions_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://datapilot-1-zxys.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(upload_router)
app.include_router(ask_router)
app.include_router(suggestions_router)
app.include_router(sessions_router)


@app.get("/status")
def status():
    """
    v1 of this project used a per-session SQLite database, and this
    endpoint checked connectivity to it via `from app.db import engine`.
    v2 (see sessions/store.py) replaced that entirely with per-session
    parquet files on disk -- there's no database anywhere in this
    codebase anymore. This endpoint was never updated when that
    migration happened, so it imported a module (app/db.py) that no
    longer exists -- meaning the app couldn't even start. Fixed by
    checking the thing v2 actually depends on instead: that the storage
    directory exists and is writable.
    """
    storage_path = Path(settings.storage_dir)
    try:
        storage_path.mkdir(parents=True, exist_ok=True)
        writable = os.access(storage_path, os.W_OK)
    except OSError:
        writable = False

    if not writable:
        raise HTTPException(status_code=503, detail="Storage directory is not writable")

    return {"status": "ok", "storage": "writable"}

# app/upload.py
#
# Three-step upload flow:
#   1. POST /upload/inspect  -- save raw files, list sheets (mostly unchanged from v1)
#   2. POST /upload/preview  -- loads the selected sheet into a dataframe,
#      runs validation + cleaning inspection, returns a report. Nothing is
#      persisted to the session store yet -- purely read-only.
#   3. POST /upload/confirm  -- loads the same dataframe again, optionally
#      applies cleaning, and persists it via app.sessions.store for the
#      /ask route to use.
#
# KNOWN LIMITATION: the v2 pipeline (planner/profiling/analysis) currently
# works on a single dataframe per session, unlike v1 which loaded every
# selected sheet as its own SQL table. Until the planner supports multiple
# named tables, selecting more than one sheet/file is rejected with a
# clear error rather than silently combining or dropping data.

import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.validation.validator import validate_dataset, ValidationError
from app.cleaning.cleaner import inspect_cleaning, apply_cleaning
from app.sessions.store import save_session_df

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOADS_DIR = Path(settings.storage_dir) / "uploads"
# Single source of truth for both is settings (app/config.py) -- this used
# to be a separately hardcoded set here, which meant changing
# settings.allowed_extensions wouldn't actually change what /upload/inspect
# accepted.
ALLOWED_EXTENSIONS = set(settings.allowed_extensions)
MAX_UPLOAD_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ---------- STEP 1: INSPECT ----------

@router.post("/upload/inspect")
async def inspect_files(files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    file_previews = []

    for file in files:
        extension = Path(file.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{extension}' for '{file.filename}'. "
                       f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        saved_path = session_dir / file.filename
        size_bytes = 0
        with open(saved_path, "wb") as f:
            # Stream in chunks and enforce the size cap while writing,
            # rather than reading the whole upload into memory first --
            # a malicious or oversized file shouldn't get fully buffered
            # in RAM before we notice it's too big.
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_SIZE_BYTES:
                    f.close()
                    shutil.rmtree(session_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=400,
                        detail=f"'{file.filename}' is larger than the "
                               f"{settings.max_upload_size_mb}MB upload limit. "
                               "Please upload a smaller file.",
                    )
                f.write(chunk)

        if extension == ".csv":
            file_previews.append({"filename": file.filename, "type": "csv", "sheets": None})
        else:
            excel_file = pd.ExcelFile(saved_path)
            file_previews.append({
                "filename": file.filename,
                "type": "excel",
                "sheets": excel_file.sheet_names,
            })

    return {"session_id": session_id, "files": file_previews}


# ---------- Shared selection models ----------

class SheetSelection(BaseModel):
    filename: str
    sheets: Optional[List[str]] = None


class PreviewRequest(BaseModel):
    session_id: str
    selections: List[SheetSelection]


class ConfirmRequest(BaseModel):
    session_id: str
    selections: List[SheetSelection]
    apply_cleaning: bool = True


# ---------- Shared loading logic ----------

def _load_selected_dataframe(session_id: str, selections: List[SheetSelection]) -> pd.DataFrame:
    """
    Loads exactly one dataframe from the user's selection.
    Raises HTTPException if the session/files are missing, or if more
    than one table worth of data was selected (see module docstring --
    multi-table isn't supported by the pipeline yet).
    """
    session_dir = UPLOADS_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found or expired. Please upload your file again.")

    to_load = []
    for selection in selections:
        file_path = session_dir / selection.filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File '{selection.filename}' not found in this session.")

        extension = file_path.suffix.lower()
        if extension == ".csv":
            to_load.append((file_path, None))
        else:
            sheets = selection.sheets or []
            for sheet_name in sheets:
                to_load.append((file_path, sheet_name))

    if len(to_load) == 0:
        raise HTTPException(status_code=400, detail="No sheets were selected.")

    if len(to_load) > 1:
        raise HTTPException(
            status_code=400,
            detail="Analyzing multiple sheets or files at once isn't supported yet. "
                   "Please select a single sheet to continue.",
        )

    file_path, sheet_name = to_load[0]
    extension = file_path.suffix.lower()
    try:
        if extension == ".csv":
            return pd.read_csv(file_path)
        return pd.read_excel(file_path, sheet_name=sheet_name)
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail="This file appears to be empty. Please check the file and try again.",
        )
    except pd.errors.ParserError as e:
        logger.warning("CSV parse error for %s: %s", file_path.name, e)
        raise HTTPException(
            status_code=400,
            detail="Could not read this file -- it may be corrupted or not a valid CSV. "
                   "Please check the file and try again.",
        )
    except ValueError as e:
        # Common for Excel: a selected sheet no longer exists, or has no
        # readable data (e.g. every row/column is genuinely blank).
        logger.warning("Excel read error for %s (sheet=%s): %s", file_path.name, sheet_name, e)
        raise HTTPException(
            status_code=400,
            detail=f"Could not read the '{sheet_name}' sheet -- it may be empty or in an unexpected format. "
                   f"Please check the file and try again." if sheet_name else
                   "Could not read this file. Please check it and try again.",
        )
    except Exception as e:
        # Catch-all: never let a raw file-parsing exception crash the
        # request uncaught. Log the real detail for debugging, return a
        # generic but honest message to the user.
        logger.warning("Unexpected error reading %s: %s", file_path.name, e)
        raise HTTPException(
            status_code=400,
            detail="Could not read this file. Please check that it's a valid CSV or Excel file and try again.",
        )


def _display_name_for_selection(selections: List[SheetSelection]) -> str:
    """Builds a human-readable name for the single loaded table, for display only.
    v2 has no real SQL tables anymore -- this exists purely so ConfirmScreen.jsx's
    existing table-name display still shows something meaningful."""
    selection = selections[0]
    base = Path(selection.filename).stem
    if selection.sheets:
        return f"{base}_{selection.sheets[0]}"
    return base


# ---------- STEP 2: PREVIEW ----------

@router.post("/upload/preview")
async def preview_upload(payload: PreviewRequest):
    df = _load_selected_dataframe(payload.session_id, payload.selections)

    try:
        validate_dataset(df)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.reason)

    report = inspect_cleaning(df)

    return {
        "rows": len(df),
        "columns": list(df.columns),
        "has_issues": report.has_issues,
        "issues": [
            {"kind": i.kind, "column": i.column, "count": i.count, "description": i.description}
            for i in report.issues
        ],
    }


# ---------- STEP 3: CONFIRM ----------

@router.post("/upload/confirm")
async def confirm_upload(payload: ConfirmRequest):
    df = _load_selected_dataframe(payload.session_id, payload.selections)

    try:
        validate_dataset(df)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.reason)

    change_log: List[str] = []
    if payload.apply_cleaning:
        df, change_log = apply_cleaning(df)

    save_session_df(payload.session_id, df)

    # Raw uploaded files are no longer needed once the working dataframe is persisted.
    session_dir = UPLOADS_DIR / payload.session_id
    shutil.rmtree(session_dir, ignore_errors=True)

    table_name = _display_name_for_selection(payload.selections)

    return {
        "session_id": payload.session_id,
        "rows": len(df),
        "columns": list(df.columns),
        "cleaning_applied": payload.apply_cleaning,
        "changes": change_log,
        # Kept as a list for compatibility with ConfirmScreen.jsx, which expects
        # tables.reduce(...) -- always exactly one entry in v2 (see multi-table
        # limitation noted in _load_selected_dataframe's docstring above).
        "tables": [
            {"table_name": table_name, "rows": len(df), "columns": list(df.columns)}
        ],
    }

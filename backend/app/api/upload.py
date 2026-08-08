# api/upload.py
#
# Three-step upload flow:
#   1. POST /upload/inspect  -- save raw files, list sheets (mostly unchanged from v1)
#   2. POST /upload/preview  -- NEW. Loads the selected sheet into a dataframe,
#      runs validation + cleaning inspection, returns a report. Nothing is
#      persisted to the session store yet -- purely read-only.
#   3. POST /upload/confirm  -- loads the same dataframe again, optionally
#      applies cleaning, and persists it via sessions.store for the /ask
#      route to use.
#
# KNOWN LIMITATION: the v2 pipeline (planner/profiling/analysis) currently
# works on a single dataframe per session, unlike v1 which loaded every
# selected sheet as its own SQL table. Until the planner supports multiple
# named tables, selecting more than one sheet/file is rejected with a
# clear error rather than silently combining or dropping data.

import shutil
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from config import settings
from validation.validator import validate_dataset, ValidationError
from cleaning.cleaner import inspect_cleaning, apply_cleaning
from sessions.store import save_session_df

router = APIRouter()

UPLOADS_DIR = Path(settings.storage_dir) / "uploads"
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


# ---------- STEP 1: INSPECT ----------

@router.post("/upload/inspect")
async def inspect_files(files: List[UploadFile] = File(...)):
    import uuid
    session_id = str(uuid.uuid4())
    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    file_previews = []

    for file in files:
        extension = Path(file.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{extension}' for '{file.filename}'."
            )

        saved_path = session_dir / file.filename
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

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

    # Flatten selections into a list of (file_path, sheet_name_or_None) to load
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
    if extension == ".csv":
        return pd.read_csv(file_path)
    return pd.read_excel(file_path, sheet_name=sheet_name)


# ---------- STEP 2: PREVIEW (new) ----------

@router.post("/upload/preview")
async def preview_upload(payload: PreviewRequest):
    df = _load_selected_dataframe(payload.session_id, payload.selections)

    try:
        validate_dataset(df)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.reason)

    report = inspect_cleaning(df)

    return {
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

    return {
        "session_id": payload.session_id,
        "rows": len(df),
        "columns": list(df.columns),
        "cleaning_applied": payload.apply_cleaning,
        "changes": change_log,
    }
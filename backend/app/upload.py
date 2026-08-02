import uuid
import sqlite3
import shutil
import pandas as pd
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

router = APIRouter()

SESSIONS_DIR = Path(__file__).parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def sanitize_table_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)


# ---------- STEP 1: INSPECT ----------

@router.post("/upload/inspect")
async def inspect_files(files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    file_previews = []

    for file in files:
        extension = Path(file.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{extension}' for '{file.filename}'."
            )

        # Save the raw file to disk so Step 2 can read it later
        saved_path = session_dir / file.filename
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        if extension == ".csv":
            file_previews.append({
                "filename": file.filename,
                "type": "csv",
                "sheets": None  # CSVs have no sheets
            })
        else:
            excel_file = pd.ExcelFile(saved_path)
            file_previews.append({
                "filename": file.filename,
                "type": "excel",
                "sheets": excel_file.sheet_names
            })

    return {
        "session_id": session_id,
        "files": file_previews
    }


# ---------- STEP 2: CONFIRM ----------
from typing import Optional

class SheetSelection(BaseModel):
    filename: str
    sheets: Optional[List[str]] = None


class ConfirmUploadRequest(BaseModel):
    session_id: str
    selections: List[SheetSelection]


@router.post("/upload/confirm")
async def confirm_upload(payload: ConfirmUploadRequest):
    session_dir = SESSIONS_DIR / payload.session_id
    db_path = SESSIONS_DIR / f"{payload.session_id}.db"

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    conn = sqlite3.connect(db_path)
    table_names = []

    for selection in payload.selections:
        file_path = session_dir / selection.filename
        extension = file_path.suffix.lower()
        base_name = sanitize_table_name(file_path.stem)

        if extension == ".csv":
            df = pd.read_csv(file_path)
            table_name = base_name
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            table_names.append({"table_name": table_name, "rows": len(df), "columns": list(df.columns)})
        else:
            excel_file = pd.ExcelFile(file_path)
            sheets_to_load = selection.sheets or excel_file.sheet_names
            for sheet_name in sheets_to_load:
                df = excel_file.parse(sheet_name)
                table_name = f"{base_name}_{sanitize_table_name(sheet_name)}"
                df.to_sql(table_name, conn, if_exists="replace", index=False)
                table_names.append({"table_name": table_name, "rows": len(df), "columns": list(df.columns)})

    conn.close()

    # Clean up raw uploaded files now that they're in SQLite
    shutil.rmtree(session_dir)

    return {
        "session_id": payload.session_id,
        "tables": table_names
    }
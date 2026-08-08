import re
import sqlite3
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from app.config import settings

router = APIRouter()
SESSIONS_DIR = Path(__file__).parent / "sessions"

client = genai.Client(api_key=settings.google_api_key)

MODEL_NAME = "gemini-3.5-flash-lite"
MAX_LOOP_ITERATIONS = 5
MAX_ROWS_TO_MODEL = 100
MAX_ROWS_TO_CHART = 50
QUERY_TIMEOUT_SECONDS = 5

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "create",
    "attach", "detach", "pragma", "vacuum", "replace", "truncate",
]


class AskRequest(BaseModel):
    session_id: str
    question: str


RUN_SQL_DECLARATION = types.FunctionDeclaration(
    name="run_sql",
    description="Run a read-only SQL SELECT query against the loaded dataset and return the results. Only SELECT statements are allowed.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "A valid SQLite SELECT query."}
        },
        "required": ["query"],
    },
)

RUN_SQL_TOOL = types.Tool(function_declarations=[RUN_SQL_DECLARATION])


def get_schema(conn) -> str:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    lines = []
    for table in tables:
        cursor.execute(f'PRAGMA table_info("{table}");')
        cols = [f"{row[1]} ({row[2]})" for row in cursor.fetchall()]
        lines.append(f'Table "{table}": ' + ", ".join(cols))
    return "\n".join(lines)


def validate_query(query: str):
    stripped = query.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("Empty query.")
    if ";" in stripped:
        raise ValueError("Multiple statements are not allowed.")
    lowered = stripped.lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT statements are allowed.")
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            raise ValueError(f"Query contains a disallowed keyword: {kw.upper()}")
    return stripped


def run_sql(conn, query: str):
    safe_query = validate_query(query)
    cursor = conn.cursor()
    cursor.execute(safe_query)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchmany(MAX_ROWS_TO_MODEL)
    safe_rows = [
        [v if isinstance(v, (int, float, str, type(None))) else str(v) for v in row]
        for row in rows
    ]
    return columns, safe_rows


DATE_HINT_KEYWORDS = ("date", "month", "year", "time", "day", "week")


def _is_date_like(column_name: str) -> bool:
    lowered = column_name.lower()
    return any(kw in lowered for kw in DATE_HINT_KEYWORDS)


def build_chart(columns, rows):
    if not rows:
        return None
    if len(columns) == 1 and len(rows) == 1:
        try:
            value = float(rows[0][0])
            return {"kind": "stat", "title": columns[0], "value": value, "labels": [], "values": []}
        except (TypeError, ValueError):
            pass
    if len(columns) >= 2 and len(rows) > 1:
        try:
            labels = [str(r[0]) for r in rows]
            values = [float(r[1]) for r in rows]
            if _is_date_like(columns[0]):
                return {"kind": "line", "title": f"{columns[1]} over {columns[0]}", "labels": labels, "values": values}
            if len(labels) <= 6:
                return {"kind": "pie", "title": f"{columns[1]} by {columns[0]}", "labels": labels, "values": values}
            return {"kind": "bar", "title": f"{columns[1]} by {columns[0]}", "labels": labels, "values": values}
        except (TypeError, ValueError):
            pass
    return {
        "kind": "table",
        "title": "Query results",
        "labels": [],
        "values": [],
        "tableColumns": columns,
        "tableRows": [[("—" if v is None else v) for v in r] for r in rows[:MAX_ROWS_TO_CHART]],
    }


def pick_best_query(query_history):
    if not query_history:
        return "", [], []
    grouped = [q for q in query_history if len(q[1]) > 1 and len(q[2]) > 1]
    if grouped:
        return grouped[-1]
    return query_history[-1]


@router.post("/ask")
def ask(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Question is too long.")

    db_path = SESSIONS_DIR / f"{payload.session_id}.db"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Session not found. Please upload your data again.")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=QUERY_TIMEOUT_SECONDS)

    try:
        schema = get_schema(conn)
        if not schema:
            raise HTTPException(status_code=400, detail="No tables found in this session. Please upload your data again.")

        system_prompt = (
            "You are a careful data analyst. You have access to a SQLite database with the "
            "following tables:\n\n"
            f"{schema}\n\n"
            "Rules:\n"
            "- Use the run_sql tool to query the data. You may call it more than once if needed.\n"
            "- Only SELECT statements are allowed — never modify data.\n"
            "- Only reference the tables and columns listed above; do not guess at columns that don't exist.\n"
            "- Prefer a single well-formed query (e.g. GROUP BY) over multiple simple ones when possible.\n"
            "- After you have enough information, give a clear, concise plain-English answer.\n"
            "- Do not include SQL syntax in your final answer text.\n"
            "- If the question cannot be answered from the available tables, say so directly instead of guessing."
        )

        contents = [types.Content(role="user", parts=[types.Part.from_text(text=question)])]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[RUN_SQL_TOOL],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        query_history = []

        for _ in range(MAX_LOOP_ITERATIONS):
            try:
                response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
            except ClientError as e:
                if e.status_code == 429:
                    raise HTTPException(status_code=429, detail="You've hit the free-tier rate limit. Wait a moment and try again.")
                raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

            function_calls = response.function_calls

            if not function_calls:
                final_text = (response.text or "").strip() or "I couldn't find an answer to that."
                best_sql, best_columns, best_rows = pick_best_query(query_history)
                chart = build_chart(best_columns, best_rows) if best_sql else None
                return {"text": final_text, "sql": best_sql, "chart": chart}

            contents.append(response.candidates[0].content)

            response_parts = []
            for fc in function_calls:
                query = fc.args.get("query", "")
                try:
                    columns, rows = run_sql(conn, query)
                    query_history.append((query, columns, rows))
                    result = {"columns": columns, "rows": rows}
                except Exception as e:
                    result = {"error": str(e)}
                response_parts.append(types.Part.from_function_response(name=fc.name, response=result))

            contents.append(types.Content(role="user", parts=response_parts))

        raise HTTPException(status_code=504, detail="Could not resolve the question in time. Try rephrasing it more simply.")

    finally:
        conn.close()
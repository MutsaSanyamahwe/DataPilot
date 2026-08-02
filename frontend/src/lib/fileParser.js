import * as XLSX from "xlsx";

export async function parseFile(file) {
  const buf = await file.arrayBuffer();
  const ext = file.name.split(".").pop()?.toLowerCase();

  if (ext === "csv" || ext === "tsv") {
    const wb = XLSX.read(buf, { type: "array", raw: false, cellDates: true });
    const sheetName = wb.SheetNames[0];
    const sheet = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: null });
    const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
    return {
      fileName: file.name,
      sheets: [
        {
          fileName: file.name,
          sheetName: sheetName || file.name,
          columns,
          rows,
        },
      ],
    };
  }

  // Excel — load all sheets
  const wb = XLSX.read(buf, { type: "array", cellDates: true });
  const sheets = wb.SheetNames.map((sheetName) => {
    const sheet = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: null });
    const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
    return { fileName: file.name, sheetName, columns, rows };
  });
  return { fileName: file.name, sheets };
}

function inferType(values) {
  const sample = values
    .filter((v) => v !== null && v !== undefined && v !== "")
    .slice(0, 50);
  if (sample.length === 0) return "string";
  if (
    sample.every(
      (v) =>
        typeof v === "number" ||
        (typeof v === "string" && !isNaN(Number(v)) && v.trim() !== ""),
    )
  ) {
    return "number";
  }
  if (
    sample.every(
      (v) =>
        v instanceof Date || (typeof v === "string" && !isNaN(Date.parse(v))),
    )
  ) {
    return "date";
  }
  if (
    sample.every(
      (v) =>
        typeof v === "boolean" ||
        v === "true" ||
        v === "false" ||
        v === "TRUE" ||
        v === "FALSE",
    )
  ) {
    return "boolean";
  }
  return "string";
}

export function buildLoadedTable(sheet) {
  const columnNames = sheet.columns;
  const columns = columnNames.map((name) => {
    const values = sheet.rows.map((r) => r[name]);
    const type = inferType(values);
    return { name, type };
  });

  // Coerce numeric strings to numbers for proper SQL typing
  const rows = sheet.rows.map((r) => {
    const out = {};
    for (const col of columns) {
      let v = r[col.name];
      if (col.type === "number" && v !== null && v !== undefined && v !== "") {
        const n = Number(v);
        if (!isNaN(n)) v = n;
      }
      out[col.name] = v;
    }
    return out;
  });

  return {
    name: sanitizeTableName(sheet.sheetName),
    source: sheet.fileName,
    rowCount: rows.length,
    columns,
    rows,
  };
}

export function sanitizeTableName(name) {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .substring(0, 40) || "data"
  );
}

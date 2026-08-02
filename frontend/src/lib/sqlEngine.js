import { PGlite } from "@electric-sql/pglite";

let db = null;

export async function getDb() {
  if (!db) {
    db = new PGlite("idb://datapilot");
  }
  return db;
}

export async function loadTables(tables) {
  const pg = await getDb();
  for (const table of tables) {
    // Drop if exists (fresh session load)
    await pg.query(`DROP TABLE IF EXISTS "${table.name}";`);
    const colDefs = table.columns.map((c) => {
      const sqlType =
        c.type === "number"
          ? "DOUBLE PRECISION"
          : c.type === "boolean"
            ? "BOOLEAN"
            : "TEXT";
      return `"${c.name}" ${sqlType}`;
    });
    await pg.query(`CREATE TABLE "${table.name}" (${colDefs.join(", ")});`);
    if (table.rows.length > 0) {
      const colNames = table.columns.map((c) => `"${c.name}"`).join(", ");
      const placeholders = table.columns.map((_, i) => `$${i + 1}`).join(", ");
      const sql = `INSERT INTO "${table.name}" (${colNames}) VALUES (${placeholders});`;
      for (const row of table.rows) {
        const params = table.columns.map((c) => row[c.name]);
        await pg.query(sql, params);
      }
    }
  }
}

export async function runQuery(sql) {
  const pg = await getDb();
  const result = await pg.query(sql);
  const cols = (result.fields ?? []).map((f) => f.name);
  return {
    columns: cols,
    rows: result.rows,
  };
}

import { runQuery } from "./sqlEngine";

function analyzeTables(tables) {
  return tables.map((table) => ({
    table,
    numericCols: table.columns
      .filter((c) => c.type === "number")
      .map((c) => c.name),
    textCols: table.columns
      .filter((c) => c.type === "string" || c.type === "boolean")
      .map((c) => c.name),
    dateCols: table.columns.filter((c) => c.type === "date").map((c) => c.name),
  }));
}

function findColumn(matches, candidates) {
  for (const m of matches) {
    for (const c of candidates) {
      const found = m.table.columns.find(
        (col) => col.name.toLowerCase() === c.toLowerCase(),
      );
      if (found) return found.name;
    }
  }
  return null;
}

function findNumericColumn(matches, candidates) {
  for (const m of matches) {
    for (const c of candidates) {
      const found = m.numericCols.find(
        (col) => col.toLowerCase() === c.toLowerCase(),
      );
      if (found) return found;
    }
  }
  for (const m of matches) {
    if (m.numericCols.length > 0) return m.numericCols[0];
  }
  return null;
}

function findGroupColumn(matches, exclude) {
  for (const m of matches) {
    const col = m.textCols.find((c) => !exclude.includes(c.toLowerCase()));
    if (col) return col;
  }
  return null;
}

function findDateColumn(matches) {
  for (const m of matches) {
    if (m.dateCols.length > 0) return m.dateCols[0];
  }
  return null;
}

const AGG_PATTERNS = [
  { test: /\b(total|sum)\b/i, agg: "SUM", label: "total" },
  { test: /\baverage\b|\bavg\b|\bmean\b/i, agg: "AVG", label: "average" },
  {
    test: /\bcount\b|\bhow many\b|\bnumber of\b/i,
    agg: "COUNT",
    label: "count",
  },
  {
    test: /\bmax(imum)?\b|\bhighest\b|\bmost\b/i,
    agg: "MAX",
    label: "maximum",
  },
  {
    test: /\bmin(imum)?\b|\blowest\b|\bleast\b/i,
    agg: "MIN",
    label: "minimum",
  },
];

export async function analyzeQuery(question, tables) {
  const matches = analyzeTables(tables);
  const q = question.toLowerCase().trim();

  if (tables.length === 0) {
    return {
      text: "No tables are loaded yet. Upload a file to start asking questions.",
      sql: "",
      error: true,
    };
  }

  // Pattern 1: "how many rows" / "how many records"
  if (
    /\bhow many (rows|records|entries|items)\b/.test(q) ||
    /\brow count\b/.test(q)
  ) {
    const t = matches[0].table;
    const sql = `SELECT COUNT(*) AS row_count FROM "${t.name}";`;
    try {
      const res = await runQuery(sql);
      const count = res.rows[0][0];
      return { text: `**${t.name}** has **${count}** rows.`, sql };
    } catch (e) {
      return { text: "I could not count the rows.", sql, error: true };
    }
  }

  // Pattern 2: "what columns" / "what fields" / "describe"
  if (
    /\bwhat (columns|fields)\b/.test(q) ||
    /\bdescribe\b|\bschema\b|\bstructure\b/.test(q)
  ) {
    const t = matches[0].table;
    const cols = t.columns.map((c) => `\`${c.name}\` (${c.type})`).join(", ");
    return {
      text: `**${t.name}** has ${t.columns.length} columns: ${cols}.`,
      sql: "",
    };
  }

  // Pattern 3: aggregation with grouping — "total X by Y", "average X per Y", "sales by region"
  for (const agg of AGG_PATTERNS) {
    if (agg.test.test(q)) {
      let valueCol = null;
      let groupCol = null;

      const byMatch = q.match(/\b(?:by|per|for each|across)\s+(\w+)/);
      if (byMatch) {
        groupCol =
          findColumn(matches, [byMatch[1]]) || findGroupColumn(matches, []);
      }

      if (agg.agg !== "COUNT") {
        for (const m of matches) {
          for (const col of m.numericCols) {
            if (q.includes(col.toLowerCase())) {
              valueCol = col;
              break;
            }
          }
        }
        if (!valueCol) valueCol = findNumericColumn(matches, []);
      }

      if (!groupCol) {
        for (const m of matches) {
          for (const col of m.textCols) {
            if (q.includes(col.toLowerCase())) {
              groupCol = col;
              break;
            }
          }
        }
      }

      const t = matches[0].table;
      const valExpr = valueCol ? `"${valueCol}"` : "*";
      const sql = groupCol
        ? `SELECT "${groupCol}", ${agg.agg}(${valExpr}) AS ${agg.label} FROM "${t.name}" GROUP BY "${groupCol}" ORDER BY ${agg.label} DESC LIMIT 20;`
        : `SELECT ${agg.agg}(${valExpr}) AS ${agg.label} FROM "${t.name}";`;

      try {
        const res = await runQuery(sql);
        if (groupCol && res.rows.length > 1) {
          const labels = res.rows.map((r) => String(r[0]));
          const values = res.rows.map((r) => Number(r[1]));
          const chart = {
            kind: "bar",
            title: `${agg.label[0].toUpperCase() + agg.label.slice(1)} of ${valueCol || "records"} by ${groupCol}`,
            labels,
            values,
          };
          const top = labels
            .slice(0, 5)
            .map((l, i) => `**${l}**: ${values[i].toLocaleString()}`)
            .join("  ·  ");
          return {
            text: `Here's the ${agg.label} of **${valueCol || "records"}** grouped by **${groupCol}**. ${top ? `Top: ${top}` : ""}`,
            sql,
            chart,
          };
        }
        const val = res.rows[0][0];
        return {
          text: `The ${agg.label} of **${valueCol || "all records"}** is **${Number(val).toLocaleString()}**.`,
          sql,
        };
      } catch {
        return {
          text: "I could not run that aggregation query.",
          sql,
          error: true,
        };
      }
    }
  }

  // Pattern 4: trend over time — "trend", "over time", "by month/day/year"
  if (
    /\b(trend|over time|by month|by day|by year|by date|time series)\b/.test(q)
  ) {
    const dateCol = findDateColumn(matches);
    const valueCol = findNumericColumn(matches, []);
    if (dateCol && valueCol) {
      const t = matches[0].table;
      const sql = `SELECT DATE_TRUNC('month', "${dateCol}") AS month, SUM("${valueCol}") AS total FROM "${t.name}" GROUP BY month ORDER BY month;`;
      try {
        const res = await runQuery(sql);
        const labels = res.rows.map((r) => String(r[0]).substring(0, 7));
        const values = res.rows.map((r) => Number(r[1]));
        const chart = {
          kind: "line",
          title: `${valueCol} over time`,
          labels,
          values,
        };
        return {
          text: `Here's the trend of **${valueCol}** over time by month.`,
          sql,
          chart,
        };
      } catch {
        // fall through
      }
    }
  }

  // Pattern 5: "show me" / "list" / "top N" — return rows
  if (/\b(show|list|display|top|first|sample|preview)\b/.test(q)) {
    const t = matches[0].table;
    const limitMatch = q.match(/\b(?:top|first|limit)\s+(\d+)/);
    const limit = limitMatch ? Math.min(parseInt(limitMatch[1]), 50) : 10;
    const sql = `SELECT * FROM "${t.name}" LIMIT ${limit};`;
    try {
      const res = await runQuery(sql);
      if (res.rows.length === 0) return { text: "No rows matched.", sql };
      const tableRows = res.rows.map((r) =>
        r.map((v) => (v === null ? "—" : String(v))),
      );
      const chart = {
        kind: "table",
        title: `${t.name} — ${limit} rows`,
        labels: [],
        values: [],
        tableColumns: res.columns,
        tableRows,
      };
      return {
        text: `Here are the first ${res.rows.length} rows from **${t.name}**.`,
        sql,
        chart,
      };
    } catch {
      return { text: "I could not retrieve those rows.", sql, error: true };
    }
  }

  // Pattern 6: "distribution of X" / "breakdown of X"
  if (/\b(distribution|breakdown|split|segments?|categories?)\b/.test(q)) {
    const groupCol = findGroupColumn(matches, []);
    if (groupCol) {
      const t = matches[0].table;
      const sql = `SELECT "${groupCol}", COUNT(*) AS count FROM "${t.name}" GROUP BY "${groupCol}" ORDER BY count DESC LIMIT 10;`;
      try {
        const res = await runQuery(sql);
        const labels = res.rows.map((r) => String(r[0]));
        const values = res.rows.map((r) => Number(r[1]));
        const chart = {
          kind: "pie",
          title: `Distribution of ${groupCol}`,
          labels,
          values,
        };
        return {
          text: `Here's the distribution of **${groupCol}**.`,
          sql,
          chart,
        };
      } catch {
        // fall through
      }
    }
  }

  // Fallback: run a SELECT * with a small limit and describe what we found
  const t = matches[0].table;
  const sql = `SELECT * FROM "${t.name}" LIMIT 5;`;
  try {
    const res = await runQuery(sql);
    const tableRows = res.rows.map((r) =>
      r.map((v) => (v === null ? "—" : String(v))),
    );
    const chart = {
      kind: "table",
      title: `${t.name} — sample rows`,
      labels: [],
      values: [],
      tableColumns: res.columns,
      tableRows,
    };
    return {
      text: `I can answer questions like "what's the total ${findNumericColumn(matches, []) || "revenue"} by ${findGroupColumn(matches, []) || "category"}?", "how many rows are there?", or "show me the top 10 rows". Here's a sample from **${t.name}**:`,
      sql,
      chart,
    };
  } catch {
    return {
      text: "I could not run a query against the loaded data. Try rephrasing your question.",
      sql,
      error: true,
    };
  }
}

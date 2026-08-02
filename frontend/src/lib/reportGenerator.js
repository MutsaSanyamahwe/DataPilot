export function generateReport(tables, messages) {
  const timestamp = new Date().toLocaleString();
  const lines = [];
  lines.push("# DataPilot Analysis Report");
  lines.push("");
  lines.push(`**Generated:** ${timestamp}`);
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push("## Loaded Datasets");
  lines.push("");
  for (const t of tables) {
    lines.push(`### ${t.name}`);
    lines.push(`- **Source:** ${t.source}`);
    lines.push(`- **Rows:** ${t.rowCount.toLocaleString()}`);
    lines.push(
      `- **Columns:** ${t.columns.map((c) => `\`${c.name}\` (${c.type})`).join(", ")}`,
    );
    lines.push("");
  }
  lines.push("---");
  lines.push("");
  lines.push("## Questions & Answers");
  lines.push("");
  const qaPairs = [];
  for (let i = 0; i < messages.length; i++) {
    if (
      messages[i].role === "user" &&
      i + 1 < messages.length &&
      messages[i + 1].role === "assistant"
    ) {
      qaPairs.push({ q: messages[i].text, a: messages[i + 1] });
    }
  }
  for (const pair of qaPairs) {
    lines.push(`### Q: ${pair.q}`);
    lines.push("");
    lines.push(pair.a.text);
    lines.push("");
    if (pair.a.sql) {
      lines.push("```sql");
      lines.push(pair.a.sql);
      lines.push("```");
      lines.push("");
    }
    if (pair.a.chart && pair.a.chart.kind !== "table") {
      lines.push(`**Chart:** ${pair.a.chart.title}`);
      lines.push("");
      if (pair.a.chart.labels && pair.a.chart.values) {
        lines.push("| Label | Value |");
        lines.push("|-------|-------|");
        for (let i = 0; i < pair.a.chart.labels.length; i++) {
          lines.push(
            `| ${pair.a.chart.labels[i]} | ${pair.a.chart.values[i]?.toLocaleString() ?? ""} |`,
          );
        }
        lines.push("");
      }
    }
    lines.push("---");
    lines.push("");
  }
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push(
    "*Your data stays in the session — nothing is stored after you're done.*",
  );
  return lines.join("\n");
}

export function downloadReport(content, filename = "datapilot-report.md") {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

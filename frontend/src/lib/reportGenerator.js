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

export function downloadReportPDF(tables, messages) {
  const timestamp = new Date().toLocaleString();

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

  const tableRowsHtml = tables
    .map(
      (t) => `
    <div style="margin-bottom:12px;">
      <strong>${t.table_name}</strong> — ${t.rows.toLocaleString()} rows<br/>
      <span style="color:#666;font-size:13px;">${t.columns.join(", ")}</span>
    </div>
  `,
    )
    .join("");

  const qaHtml = qaPairs
    .map(
      (pair) => `
    <div style="margin-bottom:28px;page-break-inside:avoid;">
      <p style="font-weight:600;margin-bottom:6px;">Q: ${escapeHtml(pair.q)}</p>
      <p style="margin-bottom:8px;">${escapeHtml(pair.a.text)}</p>
      ${pair.a.chart ? renderChartHtml(pair.a.chart) : ""}
      ${pair.a.sql ? `<pre style="background:#f4f4f4;padding:10px;border-radius:6px;font-size:12px;overflow-x:auto;margin-top:8px;">${escapeHtml(pair.a.sql)}</pre>` : ""}
    </div>
  `,
    )
    .join("");

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>DataPilot Report</title>
      <style>
        body { font-family: Arial, sans-serif; color: #111; padding: 40px; max-width: 700px; margin: auto; }
        h1 { font-size: 22px; }
        h2 { font-size: 16px; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-top: 32px; }
        table { border-collapse: collapse; width: 100%; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
        th { background: #f4f4f4; }
        @media print {
          body { padding: 0; }
        }
      </style>
    </head>
    <body>
      <h1>DataPilot Analysis Report</h1>
      <p style="color:#666;font-size:13px;">Generated: ${timestamp}</p>

      <h2>Loaded Datasets</h2>
      ${tableRowsHtml}

      <h2>Questions &amp; Answers</h2>
      ${qaHtml}

      <p style="margin-top:40px;color:#999;font-size:12px;">
        Your data stays in the session — nothing is stored after you're done.
      </p>
    </body>
    </html>
  `;

  const printWindow = window.open("", "_blank");
  printWindow.document.write(html);
  printWindow.document.close();
  printWindow.onload = () => {
    printWindow.focus();
    printWindow.print();
  };
}

function renderChartHtml(chart) {
  if (chart.kind === "stat") {
    return `
      <div style="margin:12px 0;padding:14px;border:1px solid #ddd;border-radius:8px;">
        <div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:0.05em;">${escapeHtml(chart.title || "")}</div>
        <div style="font-size:28px;font-weight:700;color:#C6852E;">${Number(chart.value).toLocaleString()}</div>
      </div>
    `;
  }

  if (chart.kind === "bar" && chart.labels?.length) {
    const max = Math.max(...chart.values, 1);
    const rows = chart.labels
      .map((label, i) => {
        const pct = Math.max((chart.values[i] / max) * 100, 2);
        return `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
          <div style="width:100px;font-size:11px;color:#444;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(label)}</div>
          <div style="flex:1;background:#eee;border-radius:3px;height:14px;">
            <div style="width:${pct}%;background:#2F9C93;height:14px;border-radius:3px;"></div>
          </div>
          <div style="width:70px;font-size:11px;color:#444;text-align:right;">${Number(chart.values[i]).toLocaleString()}</div>
        </div>
      `;
      })
      .join("");
    return `<div style="margin:12px 0;">${rows}</div>`;
  }

  if (chart.kind === "pie" && chart.labels?.length) {
    const total = chart.values.reduce((s, v) => s + v, 0) || 1;
    const rows = chart.labels
      .map((label, i) => {
        const pct = ((chart.values[i] / total) * 100).toFixed(1);
        return `
        <div style="display:flex;justify-content:space-between;font-size:12px;padding:3px 0;border-bottom:1px solid #eee;">
          <span>${escapeHtml(label)}</span>
          <span style="color:#666;">${pct}% (${Number(chart.values[i]).toLocaleString()})</span>
        </div>
      `;
      })
      .join("");
    return `<div style="margin:12px 0;max-width:300px;">${rows}</div>`;
  }

  if (chart.kind === "line" && chart.labels?.length) {
    const max = Math.max(...chart.values, 1);
    const min = Math.min(...chart.values, 0);
    const range = max - min || 1;
    const points = chart.values
      .map((v, i) => {
        const x = (i / (chart.values.length - 1 || 1)) * 280;
        const y = 60 - ((v - min) / range) * 50;
        return `${x},${y}`;
      })
      .join(" ");
    return `
      <div style="margin:12px 0;">
        <svg width="300" height="70" viewBox="0 0 300 70">
          <polyline points="${points}" fill="none" stroke="#2F9C93" stroke-width="2" />
        </svg>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#888;">
          <span>${escapeHtml(chart.labels[0])}</span>
          <span>${escapeHtml(chart.labels[chart.labels.length - 1])}</span>
        </div>
      </div>
    `;
  }

  if (chart.kind === "table" && chart.tableColumns?.length) {
    const head = chart.tableColumns
      .map((c) => `<th>${escapeHtml(c)}</th>`)
      .join("");
    const body = (chart.tableRows || [])
      .slice(0, 20)
      .map(
        (row) =>
          `<tr>${row.map((cell) => `<td>${escapeHtml(String(cell))}</td>`).join("")}</tr>`,
      )
      .join("");
    return `<table style="margin:12px 0;"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  return "";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

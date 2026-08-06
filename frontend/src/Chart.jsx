import { useRef } from 'react';

function downloadSVG(svgElement, filename) {
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgElement);
    const blob = new Blob([source], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

export function Chart({ spec }) {
    if (spec.kind === 'table') {
        return <TableChart spec={spec} />;
    }
    if (spec.kind === 'bar') {
        return <BarChart spec={spec} />;
    }
    if (spec.kind === 'line') {
        return <LineChart spec={spec} />;
    }
    if (spec.kind === 'pie') {
        return <PieChart spec={spec} />;
    }
    if (spec.kind === 'stat') {
        return <StatChart spec={spec} />;
    }
    return null;
}

function ChartCard({ title, children, onDownloadSVG }) {
    return (
        <div className="mt-3 rounded-xl surface p-4">
            <div className="mb-3 flex items-center justify-between">
                <p className="font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{title}</p>
                {onDownloadSVG && (
                    <button
                        onClick={onDownloadSVG}
                        className="font-mono text-[10px] uppercase tracking-wider hover:opacity-70 transition-opacity"
                        style={{ color: 'var(--teal)' }}
                    >
                        Download SVG
                    </button>
                )}
            </div>
            {children}
        </div>
    );
}

function StatChart({ spec }) {
    const formatted = Number.isInteger(spec.value)
        ? spec.value.toLocaleString()
        : spec.value.toLocaleString(undefined, { maximumFractionDigits: 2 });

    return (
        <ChartCard title={spec.title}>
            <p className="font-display text-4xl font-bold" style={{ color: 'var(--amber)' }}>
                {formatted}
            </p>
        </ChartCard>
    );
}

function BarChart({ spec }) {
    const max = Math.max(...spec.values, 1);
    const displayLabels = spec.labels.slice(0, 12);
    const displayValues = spec.values.slice(0, 12);

    return (
        <ChartCard title={spec.title}>
            <div className="flex items-end gap-2" style={{ height: '180px' }}>
                {displayLabels.map((label, i) => {
                    const h = (displayValues[i] / max) * 100;
                    return (
                        <div key={label + i} className="flex flex-1 flex-col items-center gap-1">
                            <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
                                {formatNum(displayValues[i])}
                            </span>
                            <div className="flex w-full flex-1 items-end">
                                <div
                                    className="w-full rounded-t-md animate-bar-grow origin-bottom"
                                    style={{
                                        height: `${h}%`,
                                        backgroundColor: 'var(--amber)',
                                        animationDelay: `${i * 0.05}s`,
                                        minHeight: '4px',
                                    }}
                                />
                            </div>
                            <span className="max-w-full truncate font-mono text-[10px]" style={{ color: 'var(--muted)' }} title={label}>
                                {label}
                            </span>
                        </div>
                    );
                })}
            </div>
        </ChartCard>
    );
}

function LineChart({ spec }) {
    const svgRef = useRef(null);
    const max = Math.max(...spec.values, 1);
    const min = Math.min(...spec.values, 0);
    const range = max - min || 1;
    const w = 100;
    const h = 160;
    const step = spec.labels.length > 1 ? w / (spec.labels.length - 1) : 0;

    const points = spec.values.map((v, i) => {
        const x = i * step;
        const y = h - ((v - min) / range) * (h - 20) - 10;
        return { x, y, v };
    });

    const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    const areaD = `${pathD} L ${w} ${h} L 0 ${h} Z`;

    return (
        <ChartCard title={spec.title} onDownloadSVG={() => downloadSVG(svgRef.current, `${spec.title || 'chart'}.svg`)}>
            <div className="relative w-full" style={{ height: '180px' }}>
                <svg ref={svgRef} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-full w-full" style={{ overflow: 'visible' }}>
                    <defs>
                        <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--teal)" stopOpacity="0.3" />
                            <stop offset="100%" stopColor="var(--teal)" stopOpacity="0" />
                        </linearGradient>
                    </defs>
                    <path d={areaD} fill="url(#lineGrad)" />
                    <path d={pathD} fill="none" stroke="var(--teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    {points.map((p, i) => (
                        <circle key={i} cx={p.x} cy={p.y} r="1.5" fill="var(--teal)" />
                    ))}
                </svg>
            </div>
            <div className="mt-2 flex justify-between">
                <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{spec.labels[0]}</span>
                <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{spec.labels[spec.labels.length - 1]}</span>
            </div>
        </ChartCard>
    );
}

function PieChart({ spec }) {
    const total = spec.values.reduce((s, v) => s + v, 0) || 1;
    let cumulative = 0;
    const colors = ['var(--amber)', 'var(--teal)', 'var(--amber-light)', 'var(--teal-dark)', 'var(--amber-dark)', 'var(--teal-muted)'];

    const slices = spec.labels.slice(0, 8).map((label, i) => {
        const value = spec.values[i];
        const pct = value / total;
        const startAngle = cumulative * 2 * Math.PI - Math.PI / 2;
        cumulative += pct;
        const endAngle = cumulative * 2 * Math.PI - Math.PI / 2;
        const x1 = 50 + 40 * Math.cos(startAngle);
        const y1 = 50 + 40 * Math.sin(startAngle);
        const x2 = 50 + 40 * Math.cos(endAngle);
        const y2 = 50 + 40 * Math.sin(endAngle);
        const largeArc = pct > 0.5 ? 1 : 0;
        const path = `M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`;
        return { label, value, pct, path, color: colors[i % colors.length] };
    });

    return (
        <ChartCard title={spec.title}>
            <div className="flex items-center gap-6">
                <svg viewBox="0 0 100 100" className="h-32 w-32 shrink-0">
                    {slices.map((s, i) => (
                        <path key={i} d={s.path} fill={s.color} stroke="var(--surface)" strokeWidth="0.5" />
                    ))}
                </svg>
                <div className="flex-1 space-y-1.5">
                    {slices.map((s, i) => (
                        <div key={i} className="flex items-center gap-2">
                            <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
                            <span className="flex-1 truncate font-mono text-xs">{s.label}</span>
                            <span className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                {(s.pct * 100).toFixed(1)}%
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </ChartCard>
    );
}

function TableChart({ spec }) {
    const cols = spec.tableColumns || [];
    const rows = spec.tableRows || [];
    const displayRows = rows.slice(0, 50);

    return (
        <ChartCard title={spec.title}>
            <div className="max-h-64 overflow-auto scroll-thin rounded-lg" style={{ border: '1px solid var(--border)' }}>
                <table className="w-full">
                    <thead className="sticky top-0" style={{ background: 'var(--bg)' }}>
                        <tr>
                            {cols.map((c) => (
                                <th key={c} className="px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)', borderBottom: '1px solid var(--border)' }}>
                                    {c}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {displayRows.map((row, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                {row.map((cell, j) => (
                                    <td key={j} className="px-3 py-1.5 font-mono text-xs" style={{ color: 'var(--text)' }}>
                                        {cell}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {rows.length > displayRows.length && (
                <p className="mt-2 font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
                    Showing {displayRows.length} of {rows.length} rows
                </p>
            )}
        </ChartCard>
    );
}

function formatNum(n) {
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'k';
    return n.toLocaleString();
}
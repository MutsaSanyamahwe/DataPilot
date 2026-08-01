import { useState } from 'react';
import { ArrowRight, ArrowLeft, Table2, Hash, Check, Loader2 } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { loadTables } from './lib/sqlEngine';

export function ConfirmScreen({ theme, onToggleTheme, onBack, tables, onProceed }) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleProceed = async () => {
        setLoading(true);
        setError(null);
        try {
            await loadTables(tables);
            onProceed();
        } catch {
            setError('Could not load data into the analysis engine. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const totalRows = tables.reduce((sum, t) => sum + t.rowCount, 0);
    const totalCols = tables.reduce((sum, t) => sum + t.columns.length, 0);

    return (
        <div className="flex min-h-screen flex-col">
            <nav className="flex items-center justify-between px-6 py-5 md:px-10">
                <div className="flex items-center gap-4">
                    <button onClick={onBack} className="font-mono text-xs uppercase tracking-wider transition-opacity hover:opacity-60" style={{ color: 'var(--muted)' }}>
                        ← Back
                    </button>
                    <span className="h-4 w-px" style={{ backgroundColor: 'var(--border)' }} />
                    <Logo onClick={onBack} />
                </div>
                <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            </nav>

            <main className="flex flex-1 items-center justify-center px-6 pb-10">
                <div className="w-full max-w-3xl">
                    <div className="mb-6 text-center animate-fade-in">
                        <span className="eyebrow">Step 3 — Confirm</span>
                        <h1 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
                            Data loaded successfully
                        </h1>
                        <p className="mt-2 font-body text-sm" style={{ color: 'var(--muted)' }}>
                            {tables.length} {tables.length === 1 ? 'table' : 'tables'} · {totalRows.toLocaleString()} rows · {totalCols} columns ready for analysis.
                        </p>
                    </div>

                    {/* Summary stats */}
                    <div className="mb-5 grid grid-cols-3 gap-3 animate-fade-in">
                        <StatCard label="Tables" value={tables.length.toString()} icon={<Table2 size={16} />} />
                        <StatCard label="Total rows" value={totalRows.toLocaleString()} icon={<Hash size={16} />} />
                        <StatCard label="Columns" value={totalCols.toString()} icon={<Check size={16} />} />
                    </div>

                    {/* Table cards */}
                    <div className="space-y-4">
                        {tables.map((table, idx) => (
                            <div key={table.name} className="rounded-2xl surface p-5 animate-fade-in" style={{ animationDelay: `${idx * 0.08}s` }}>
                                <div className="mb-3 flex items-center gap-2">
                                    <Table2 size={18} style={{ color: 'var(--teal)' }} />
                                    <span className="font-display text-base font-semibold">{table.name}</span>
                                    <span className="ml-auto font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                        {table.rowCount.toLocaleString()} rows
                                    </span>
                                </div>
                                <p className="mb-3 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                    Source: {table.source}
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                    {table.columns.map((col) => (
                                        <span
                                            key={col.name}
                                            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-xs"
                                            style={{
                                                backgroundColor: 'var(--bg)',
                                                border: '1px solid var(--border)',
                                            }}
                                        >
                                            {col.name}
                                            <span
                                                className="rounded px-1 text-[10px] uppercase"
                                                style={{
                                                    backgroundColor: col.type === 'number' ? 'var(--amber-soft)' : col.type === 'date' ? 'var(--teal-soft)' : 'var(--border)',
                                                    color: col.type === 'number' ? 'var(--amber)' : col.type === 'date' ? 'var(--teal)' : 'var(--muted)',
                                                }}
                                            >
                                                {col.type}
                                            </span>
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>

                    {error && (
                        <p className="mt-4 text-center font-mono text-xs" style={{ color: 'var(--amber)' }}>
                            {error}
                        </p>
                    )}

                    {/* Actions */}
                    <div className="mt-6 flex items-center justify-between animate-fade-in">
                        <button
                            onClick={onBack}
                            className="inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider transition-opacity hover:opacity-60"
                            style={{ color: 'var(--muted)' }}
                        >
                            <ArrowLeft size={14} />
                            Back
                        </button>
                        <button
                            onClick={handleProceed}
                            disabled={loading}
                            className="btn-amber inline-flex items-center gap-2 rounded-xl px-6 py-3 font-display text-sm font-semibold disabled:opacity-60"
                        >
                            {loading ? (
                                <>
                                    <Loader2 size={16} className="animate-spin-slow" />
                                    Loading into engine...
                                </>
                            ) : (
                                <>
                                    Start analyzing
                                    <ArrowRight size={16} strokeWidth={2.5} />
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </main>

            <footer className="px-6 py-5 text-center">
                <p className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                    Your data stays in the session — nothing is stored after you're done.
                </p>
            </footer>
        </div>
    );
}

function StatCard({ label, value, icon }) {
    return (
        <div className="rounded-xl surface p-4 text-center">
            <div className="mb-1 flex justify-center" style={{ color: 'var(--amber)' }}>{icon}</div>
            <p className="font-display text-2xl font-bold">{value}</p>
            <p className="font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{label}</p>
        </div>
    );
}
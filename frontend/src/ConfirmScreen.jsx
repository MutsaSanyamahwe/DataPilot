import { useEffect, useState } from 'react';
import { ArrowRight, ArrowLeft, Table2, Hash, AlertTriangle, Sparkles, Check, Loader2, X } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';

const API_BASE = 'https://datapilot-opfy.onrender.com';

// sessionId + selections come from InspectScreen's handoff.
// onProceed(data) is called once /upload/confirm actually succeeds.
export function ConfirmScreen({ theme, onToggleTheme, onBack, sessionId, selections, onProceed }) {
    const [phase, setPhase] = useState('loading'); // 'loading' | 'ready' | 'error'
    const [preview, setPreview] = useState(null); // { rows, columns, has_issues, issues }
    const [applyCleaning, setApplyCleaning] = useState(true);
    const [confirming, setConfirming] = useState(false);
    const [error, setError] = useState(null);
    const [showLeaveAsIsWarning, setShowLeaveAsIsWarning] = useState(false);

    useEffect(() => {
        let cancelled = false;

        const loadPreview = async () => {
            setPhase('loading');
            setError(null);
            try {
                const res = await fetch(`${API_BASE}/upload/preview`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, selections }),
                });
                if (!res.ok) {
                    const body = await res.json().catch(() => null);
                    throw new Error(body?.detail || `Server error: ${res.status}`);
                }
                const data = await res.json();
                if (cancelled) return;
                setPreview(data);
                setPhase('ready');
            } catch (err) {
                if (cancelled) return;
                setError(err.message || 'Could not load a preview of your data.');
                setPhase('error');
            }
        };

        loadPreview();
        return () => { cancelled = true; };
    }, [sessionId, selections]);

    const handleStartAnalyzing = async () => {
        setConfirming(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/upload/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, selections, apply_cleaning: applyCleaning }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail || `Server error: ${res.status}`);
            }
            const data = await res.json();
            onProceed(data);
        } catch (err) {
            setError(err.message || 'Could not load the selected data.');
        } finally {
            setConfirming(false);
        }
    };

    // Clicking "Leave as-is" doesn't apply the choice immediately -- it opens
    // a warning first, since this is the riskier option and deserves a
    // deliberate second confirmation rather than a single click.
    const handleLeaveAsIsClick = () => setShowLeaveAsIsWarning(true);

    const confirmLeaveAsIs = () => {
        setApplyCleaning(false);
        setShowLeaveAsIsWarning(false);
    };

    const cancelLeaveAsIs = () => setShowLeaveAsIsWarning(false);

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
                <div className="w-full max-w-2xl">
                    {phase === 'loading' && (
                        <div className="flex flex-col items-center gap-3 py-16 animate-fade-in">
                            <Loader2 size={24} className="animate-spin-slow" style={{ color: 'var(--muted)' }} />
                            <p className="font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                Checking your data...
                            </p>
                        </div>
                    )}

                    {phase === 'error' && (
                        <div className="py-16 text-center animate-fade-in">
                            <p className="font-body text-sm" style={{ color: 'var(--amber)' }}>{error}</p>
                            <button
                                onClick={onBack}
                                className="mt-4 inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider transition-opacity hover:opacity-60"
                                style={{ color: 'var(--muted)' }}
                            >
                                <ArrowLeft size={14} />
                                Back to sheet selection
                            </button>
                        </div>
                    )}

                    {phase === 'ready' && preview && (
                        <>
                            <div className="mb-6 text-center animate-fade-in">
                                <span className="eyebrow">Step 3 — Confirm</span>
                                <h1 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
                                    {preview.has_issues ? 'A few things we noticed' : 'Ready to load'}
                                </h1>
                                <p className="mt-2 font-body text-sm" style={{ color: 'var(--muted)' }}>
                                    {preview.has_issues
                                        ? `${preview.issues.length} ${preview.issues.length === 1 ? 'issue' : 'issues'} found. Nothing has been changed yet.`
                                        : `${preview.rows.toLocaleString()} rows · ${preview.columns.length} columns ready for analysis.`}
                                </p>
                            </div>

                            <div className="mb-5 grid grid-cols-2 gap-3 animate-fade-in">
                                <StatCard label="Rows" value={preview.rows.toLocaleString()} icon={<Hash size={16} />} />
                                <StatCard label="Columns" value={preview.columns.length.toString()} icon={<Table2 size={16} />} />
                            </div>

                            <div className="mb-5 rounded-2xl surface p-4 animate-fade-in">
                                <div className="mb-3 flex items-center gap-2">
                                    <Table2 size={16} style={{ color: 'var(--teal)' }} />
                                    <span className="font-display text-sm font-semibold">Columns</span>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                    {preview.columns.map((col) => (
                                        <span
                                            key={col}
                                            className="inline-flex items-center rounded-md px-2 py-1 font-mono text-xs"
                                            style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}
                                        >
                                            {col}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {preview.has_issues && (
                                <div className="mb-5 space-y-2 animate-fade-in">
                                    {preview.issues.map((issue, i) => (
                                        <div key={i} className="flex items-start gap-3 rounded-xl surface p-3.5">
                                            <AlertTriangle size={16} strokeWidth={2} style={{ color: 'var(--amber)', marginTop: '1px', flexShrink: 0 }} />
                                            <p className="font-body text-sm">{issue.description}</p>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {preview.has_issues && (
                                <div className="mb-5 space-y-2 animate-fade-in">
                                    <button
                                        onClick={() => setApplyCleaning(true)}
                                        className="flex w-full items-center gap-3 rounded-xl px-4 py-3.5 text-left transition-all"
                                        style={{
                                            border: `1px solid ${applyCleaning ? 'var(--teal)' : 'var(--border)'}`,
                                            background: applyCleaning ? 'var(--teal-soft, rgba(45,158,158,0.08))' : 'transparent',
                                        }}
                                    >
                                        <div
                                            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors"
                                            style={{
                                                borderColor: applyCleaning ? 'var(--teal)' : 'var(--border)',
                                                backgroundColor: applyCleaning ? 'var(--teal)' : 'transparent',
                                                color: 'var(--bg)',
                                            }}
                                        >
                                            {applyCleaning && <Check size={12} strokeWidth={3} />}
                                        </div>
                                        <Sparkles size={16} style={{ color: 'var(--teal)', flexShrink: 0 }} />
                                        <div>
                                            <p className="font-display text-sm font-semibold">Clean automatically</p>
                                            <p className="font-body text-xs" style={{ color: 'var(--muted)' }}>
                                                Recommended — fixes these issues before analysis
                                            </p>
                                        </div>
                                    </button>

                                    <button
                                        onClick={handleLeaveAsIsClick}
                                        className="flex w-full items-center gap-3 rounded-xl px-4 py-3.5 text-left transition-all"
                                        style={{
                                            border: `1px solid ${!applyCleaning ? 'var(--amber)' : 'var(--border)'}`,
                                            background: !applyCleaning ? 'var(--amber-soft)' : 'transparent',
                                        }}
                                    >
                                        <div
                                            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors"
                                            style={{
                                                borderColor: !applyCleaning ? 'var(--amber)' : 'var(--border)',
                                                backgroundColor: !applyCleaning ? 'var(--amber)' : 'transparent',
                                                color: 'var(--bg)',
                                            }}
                                        >
                                            {!applyCleaning && <Check size={12} strokeWidth={3} />}
                                        </div>
                                        <div>
                                            <p className="font-display text-sm font-semibold">Leave as-is</p>
                                            <p className="font-body text-xs" style={{ color: 'var(--muted)' }}>
                                                Load the data exactly as uploaded
                                            </p>
                                        </div>
                                    </button>
                                </div>
                            )}

                            {error && (
                                <p className="mb-4 text-center font-mono text-xs" style={{ color: 'var(--amber)' }}>
                                    {error}
                                </p>
                            )}

                            <div className="flex items-center justify-between animate-fade-in">
                                <button
                                    onClick={onBack}
                                    className="inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider transition-opacity hover:opacity-60"
                                    style={{ color: 'var(--muted)' }}
                                >
                                    <ArrowLeft size={14} />
                                    Back
                                </button>
                                <button
                                    onClick={handleStartAnalyzing}
                                    disabled={confirming}
                                    className="btn-amber inline-flex items-center gap-2 rounded-xl px-6 py-3 font-display text-sm font-semibold disabled:opacity-50"
                                >
                                    {confirming ? (
                                        <>
                                            <Loader2 size={16} className="animate-spin-slow" />
                                            Loading...
                                        </>
                                    ) : (
                                        <>
                                            Start analyzing
                                            <ArrowRight size={16} strokeWidth={2.5} />
                                        </>
                                    )}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </main>

            <footer className="px-6 py-5 text-center">
                <p className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                    Your data stays in the session — nothing is stored after you're done.
                </p>
            </footer>

            {showLeaveAsIsWarning && (
                <LeaveAsIsWarningModal
                    issues={preview?.issues || []}
                    onCancel={cancelLeaveAsIs}
                    onConfirm={confirmLeaveAsIs}
                />
            )}
        </div>
    );
}

function LeaveAsIsWarningModal({ issues, onCancel, onConfirm }) {
    // Build specific, concrete consequences from the actual issues found,
    // rather than a generic warning -- this is what makes the trade-off real
    // instead of abstract.
    const hasKind = (kind) => issues.some((i) => i.kind === kind);

    const consequences = [];
    if (hasKind('duplicate_rows')) {
        consequences.push('Duplicate rows will be counted twice in totals, averages, and counts.');
    }
    if (hasKind('inconsistent_nulls')) {
        consequences.push('Inconsistent blank values (like "N/A" and "-") will stay as separate, mismatched entries instead of being treated as missing.');
    }
    if (hasKind('whitespace')) {
        consequences.push('Values with extra spaces (like " Engineering" and "Engineering") will be treated as different categories in charts and groupings.');
    }
    if (consequences.length === 0) {
        consequences.push('The issues listed above will remain in your data exactly as uploaded.');
    }

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-6"
            style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
            onClick={onCancel}
        >
            <div
                className="w-full max-w-md rounded-2xl surface p-6 animate-fade-in"
                style={{ border: '1px solid var(--amber)' }}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="mb-4 flex items-start justify-between">
                    <div className="flex items-center gap-2.5">
                        <div
                            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                            style={{ backgroundColor: 'var(--amber-soft)' }}
                        >
                            <AlertTriangle size={18} style={{ color: 'var(--amber)' }} />
                        </div>
                        <h2 className="font-display text-lg font-bold">Leave data as-is?</h2>
                    </div>
                    <button
                        onClick={onCancel}
                        className="rounded-lg p-1 transition-opacity hover:opacity-60"
                        style={{ color: 'var(--muted)' }}
                        aria-label="Close"
                    >
                        <X size={18} />
                    </button>
                </div>

                <p className="mb-3 font-body text-sm" style={{ color: 'var(--muted)' }}>
                    If you skip cleaning, this will directly affect your analysis:
                </p>

                <ul className="mb-5 space-y-2">
                    {consequences.map((text, i) => (
                        <li key={i} className="flex items-start gap-2.5 font-body text-sm">
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ backgroundColor: 'var(--amber)' }} />
                            {text}
                        </li>
                    ))}
                </ul>

                <div
                    className="mb-5 flex items-center gap-2 rounded-lg px-3 py-2.5"
                    style={{ backgroundColor: 'var(--teal-soft, rgba(45,158,158,0.08))' }}
                >
                    <Sparkles size={14} style={{ color: 'var(--teal)', flexShrink: 0 }} />
                    <p className="font-body text-xs" style={{ color: 'var(--muted)' }}>
                        We recommend cleaning automatically — it only affects formatting, not your actual values.
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={onCancel}
                        className="flex-1 rounded-xl px-4 py-2.5 font-display text-sm font-semibold transition-colors"
                        style={{ backgroundColor: 'var(--teal)', color: 'var(--bg)' }}
                    >
                        Clean instead
                    </button>
                    <button
                        onClick={onConfirm}
                        className="flex-1 rounded-xl px-4 py-2.5 font-display text-sm font-semibold transition-all"
                        style={{ border: '1px solid var(--border)', color: 'var(--muted)' }}
                    >
                        Leave as-is anyway
                    </button>
                </div>
            </div>
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

import { useState, useRef, useEffect } from 'react';
import {
    Send, Download, Loader2, Table2, Sparkles, Database, ArrowUpRight,
    Compass, X, AlertTriangle,
} from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { Chart } from './Chart';
import { generateReport, downloadReport, downloadReportPDF } from './lib/reportGenerator';

const API_BASE = 'https://datapilot-opfy.onrender.com';

const INITIAL_OVERVIEW_QUESTION = 'Give me an overview of this dataset, including what kinds of columns it has.';

// Groups the flat list of { question, operation } suggestions returned by
// GET /suggested_questions/:sessionId into labeled sections for the
// sidebar, purely for display -- the backend is the one deciding WHICH
// questions are safe to suggest (see app/suggestions/generator.py), this
// just organizes them. Falls back to "More" for any operation not listed
// here so a newly-added backend operation never silently disappears.
const CATEGORY_BY_OPERATION = {
    describe: 'Overview',
    duplicate_rows: 'Overview',
    top_n: 'Rows',
    sample: 'Rows',
    filter: 'Rows',
    distinct: 'Categories',
    distribution: 'Categories',
    groupby_agg: 'Numbers',
    outlier_detection: 'Numbers',
    trend: 'Trends',
    date_range_filter: 'Trends',
    correlation: 'Relationships',
    pivot: 'Relationships',
    comparison: 'Comparisons',
};

function groupSuggestionsByCategory(questions) {
    const order = [];
    const byCategory = {};

    for (const { question, operation } of questions) {
        const category = CATEGORY_BY_OPERATION[operation] || 'More';
        if (!byCategory[category]) {
            byCategory[category] = [];
            order.push(category);
        }
        byCategory[category].push(question);
    }

    return order.map((category) => ({ category, questions: byCategory[category] }));
}

export function ChatScreen({ theme, onToggleTheme, onBack, sessionId, tables }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [initialLoading, setInitialLoading] = useState(true);
    const [reportMenuOpen, setReportMenuOpen] = useState(false);
    // Explore starts open the moment the chat screen mounts -- same idea
    // as Claude's own chat-history sidebar: visible by default, user can
    // collapse it via the same Compass toggle if they want more room.
    const [exploreOpen, setExploreOpen] = useState(true);
    const [exploreSections, setExploreSections] = useState([]);
    const [exploreLoading, setExploreLoading] = useState(true);
    const [showExitConfirm, setShowExitConfirm] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [messages, loading]);

    // Auto-load a description of the dataset the moment the chat screen
    // mounts, so the first thing the user sees is real, useful context
    // instead of a blank hero. Runs once per session -- if it fails for
    // any reason, fail silently into the normal empty state below rather
    // than showing an error as literally the first thing the user sees.
    useEffect(() => {
        let cancelled = false;

        const loadInitialOverview = async () => {
            try {
                const res = await fetch(`${API_BASE}/ask`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, question: INITIAL_OVERVIEW_QUESTION, history: [] }),
                });
                if (!res.ok) throw new Error('overview request failed');
                const result = await res.json();
                if (cancelled) return;
                setMessages([{
                    id: crypto.randomUUID(),
                    role: 'assistant',
                    text: result.text,
                    chart: result.chart,
                    followUpQuestions: result.follow_up_questions || [],
                }]);
            } catch {
                // Silent -- normal empty state with suggested questions covers this.
            } finally {
                if (!cancelled) setInitialLoading(false);
            }
        };

        loadInitialOverview();
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    // Loads the "Explore" sidebar's suggested questions straight from the
    // backend (app/suggestions/generator.py + service.py) -- these are
    // guaranteed-answerable questions, polished by an LLM pass into more
    // natural phrasing. Runs once per session, independent of the
    // overview load above so a slow/failed overview doesn't hold up the
    // sidebar (or vice versa).
    useEffect(() => {
        let cancelled = false;

        const loadSuggestions = async () => {
            try {
                const res = await fetch(`${API_BASE}/suggested_questions/${sessionId}`);
                if (!res.ok) throw new Error('suggestions request failed');
                const result = await res.json();
                if (cancelled) return;
                setExploreSections(groupSuggestionsByCategory(result.questions || []));
            } catch {
                // Silent -- sidebar already handles an empty section list gracefully.
                if (!cancelled) setExploreSections([]);
            } finally {
                if (!cancelled) setExploreLoading(false);
            }
        };

        loadSuggestions();
        return () => { cancelled = true; };
    }, [sessionId]);

    const sendQuestion = async (question) => {
        const q = question.trim();
        if (!q || loading) return;

        const history = messages
            .filter((m) => !m.error)
            .slice(-6)
            .map((m) => ({ role: m.role, text: m.text }));

        const userMsg = { id: crypto.randomUUID(), role: 'user', text: q };
        setMessages((prev) => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const res = await fetch(`${API_BASE}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, question: q, history }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail || `Server error: ${res.status}`);
            }
            const result = await res.json();
            const assistantMsg = {
                id: crypto.randomUUID(),
                role: 'assistant',
                text: result.text,
                chart: result.chart,
                followUpQuestions: result.follow_up_questions || [],
            };
            setMessages((prev) => [...prev, assistantMsg]);
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                {
                    id: crypto.randomUUID(),
                    role: 'assistant',
                    text: err.message || 'Something went wrong answering that. Try rephrasing.',
                    error: true,
                },
            ]);
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadMarkdown = () => {
        const report = generateReport(tables, messages);
        downloadReport(report);
        setReportMenuOpen(false);
    };

    const handleDownloadPDF = () => {
        downloadReportPDF(tables, messages);
        setReportMenuOpen(false);
    };

    // Only interrupt with a confirmation if there's actually something to
    // lose -- no point warning about an empty conversation.
    const handleBackClick = () => {
        if (messages.length > 0) {
            setShowExitConfirm(true);
        } else {
            onBack();
        }
    };

    const hasMessages = messages.length > 0;

    return (
        <div className="flex h-screen flex-col">
            {/* Nav */}
            <nav className="flex shrink-0 items-center justify-between px-6 py-4 md:px-10">
                <div className="flex items-center gap-4">
                    <button onClick={handleBackClick} className="font-mono text-xs uppercase tracking-wider transition-opacity hover:opacity-60" style={{ color: 'var(--muted)' }}>
                        ← New session
                    </button>
                    <span className="h-4 w-px" style={{ backgroundColor: 'var(--border)' }} />
                    <Logo onClick={handleBackClick} />
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setExploreOpen((v) => !v)}
                        className="inline-flex items-center gap-1.5 rounded-lg surface px-3 py-1.5 font-mono text-xs font-medium transition-all hover:opacity-80"
                        style={{ border: `1px solid ${exploreOpen ? 'var(--amber)' : 'var(--border)'}` }}
                    >
                        <Compass size={13} style={{ color: 'var(--amber)' }} />
                        Explore
                    </button>

                    {hasMessages && (
                        <div className="relative">
                            <button
                                onClick={() => setReportMenuOpen((v) => !v)}
                                className="inline-flex items-center gap-1.5 rounded-lg surface px-3 py-1.5 font-mono text-xs font-medium transition-all hover:opacity-80"
                            >
                                <Download size={13} style={{ color: 'var(--teal)' }} />
                                Report
                            </button>
                            {reportMenuOpen && (
                                <div
                                    className="absolute right-0 top-full mt-1 rounded-lg surface overflow-hidden z-30"
                                    style={{ minWidth: '140px' }}
                                >
                                    <button
                                        onClick={handleDownloadMarkdown}
                                        className="w-full text-left px-3 py-2 font-mono text-xs hover:opacity-70 transition-opacity"
                                    >
                                        Markdown (.md)
                                    </button>
                                    <button
                                        onClick={handleDownloadPDF}
                                        className="w-full text-left px-3 py-2 font-mono text-xs hover:opacity-70 transition-opacity"
                                        style={{ borderTop: '1px solid var(--border)' }}
                                    >
                                        PDF (.pdf)
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                    <ThemeToggle theme={theme} onToggle={onToggleTheme} />
                </div>
            </nav>

            {/* Tables context bar -- static info pills, no longer interactive.
                (Used to expand into a column-list popover on click; removed
                per request -- these are now just a "what's loaded" readout.) */}
            <div className="flex shrink-0 items-center gap-2 overflow-x-auto px-6 py-2 scroll-thin" style={{ borderBottom: '1px solid var(--border)' }}>
                <span className="font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Loaded:
                </span>
                {tables.map((t) => (
                    <div
                        key={t.table_name}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-xs"
                        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
                    >
                        <Table2 size={11} style={{ color: 'var(--teal)' }} />
                        {t.table_name}
                        <span style={{ color: 'var(--muted)' }}>· {t.rows.toLocaleString()}</span>
                    </div>
                ))}
            </div>

            {/* Main area: chat column + explore sidebar side by side.
                The input bar lives INSIDE the chat column (not as a sibling
                spanning full width below both) so it shrinks/repositions
                together with the chat area whenever the sidebar opens or
                closes, instead of sitting full-width underneath it. */}
            <div className="relative flex flex-1 overflow-hidden">
                <div className="flex flex-1 flex-col overflow-hidden">
                    {/* Chat area */}
                    <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-thin px-6 py-6">
                        <div className="mx-auto max-w-3xl">
                            {initialLoading && (
                                <div className="flex flex-col items-center justify-center gap-3 py-16 animate-fade-in">
                                    <Loader2 size={22} className="animate-spin-slow" style={{ color: 'var(--muted)' }} />
                                    <p className="font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                        Looking over your data...
                                    </p>
                                </div>
                            )}

                            {!initialLoading && !hasMessages && (
                                <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
                                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full" style={{ background: 'var(--amber-soft)' }}>
                                        <Sparkles size={28} style={{ color: 'var(--amber)' }} />
                                    </div>
                                    <h2 className="font-display text-2xl font-bold">Ask anything about your data</h2>
                                    <p className="mt-2 max-w-md font-body text-sm" style={{ color: 'var(--muted)' }}>
                                        I'll figure out the right analysis, run it directly against your data, and explain what I find — with charts when useful.
                                    </p>
                                </div>
                            )}

                            {!initialLoading && messages.map((msg) => (
                                <MessageBubble key={msg.id} msg={msg} onFollowUpClick={sendQuestion} />
                            ))}

                            {loading && (
                                <div className="flex items-center gap-2 py-3 animate-fade-in">
                                    <div className="flex h-8 w-8 items-center justify-center rounded-full" style={{ background: 'var(--amber-soft)' }}>
                                        <Database size={14} style={{ color: 'var(--amber)' }} />
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <Loader2 size={14} className="animate-spin-slow" style={{ color: 'var(--muted)' }} />
                                        <span className="font-mono text-xs" style={{ color: 'var(--muted)' }}>Analyzing...</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Input bar -- now scoped to the chat column's width */}
                    <div className="shrink-0 px-6 py-4" style={{ borderTop: '1px solid var(--border)' }}>
                        <div className="mx-auto max-w-3xl">
                            <form
                                onSubmit={(e) => { e.preventDefault(); sendQuestion(input); }}
                                className="flex items-center gap-2"
                            >
                                <div className="flex flex-1 items-center rounded-xl surface px-4 py-2.5" style={{ borderColor: 'var(--border)' }}>
                                    <input
                                        value={input}
                                        onChange={(e) => setInput(e.target.value)}
                                        placeholder="Ask a question about your data..."
                                        className="w-full bg-transparent font-body text-sm outline-none"
                                        style={{ color: 'var(--text)' }}
                                        disabled={loading}
                                    />
                                </div>
                                <button
                                    type="submit"
                                    disabled={!input.trim() || loading}
                                    className="btn-amber flex h-11 w-11 items-center justify-center rounded-xl disabled:opacity-40"
                                >
                                    <Send size={18} strokeWidth={2.25} />
                                </button>
                            </form>
                        </div>
                    </div>
                </div>

                {/* Explore sidebar -- collapsible, slides in from the right */}
                <ExploreSidebar
                    open={exploreOpen}
                    onClose={() => setExploreOpen(false)}
                    sections={exploreSections}
                    loading={exploreLoading}
                    onSelectQuestion={(q) => {
                        sendQuestion(q);
                    }}
                />
            </div>

            {showExitConfirm && (
                <ExitConfirmModal
                    onCancel={() => setShowExitConfirm(false)}
                    onConfirm={() => {
                        setShowExitConfirm(false);
                        onBack();
                    }}
                />
            )}
        </div>
    );
}

function ExploreSidebar({ open, onClose, sections, loading, onSelectQuestion }) {
    return (
        <div
            className="shrink-0 overflow-hidden transition-all duration-300 ease-out"
            style={{
                width: open ? '300px' : '0px',
                borderLeft: open ? '1px solid var(--border)' : 'none',
            }}
        >
            <div className="flex h-full w-75 flex-col">
                <div className="flex shrink-0 items-center justify-between px-4 py-3.5" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex items-center gap-2">
                        <Compass size={15} style={{ color: 'var(--amber)' }} />
                        <span className="font-display text-sm font-semibold">Explore your data</span>
                    </div>
                    <button onClick={onClose} className="rounded-md p-1 transition-opacity hover:opacity-60" style={{ color: 'var(--muted)' }} aria-label="Close">
                        <X size={16} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto scroll-thin px-4 py-4">
                    {loading && (
                        <div className="flex items-center gap-2 py-4">
                            <Loader2 size={14} className="animate-spin-slow" style={{ color: 'var(--muted)' }} />
                            <span className="font-mono text-xs" style={{ color: 'var(--muted)' }}>Loading suggestions...</span>
                        </div>
                    )}
                    {!loading && sections.length === 0 && (
                        <p className="font-body text-xs" style={{ color: 'var(--muted)' }}>
                            No suggestions available yet.
                        </p>
                    )}
                    <div className="space-y-5">
                        {sections.map((section) => (
                            <div key={section.category}>
                                <p className="mb-2 font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                    {section.category}
                                </p>
                                <div className="space-y-1.5">
                                    {section.questions.map((q) => (
                                        <button
                                            key={q}
                                            onClick={() => onSelectQuestion(q)}
                                            className="w-full rounded-lg px-3 py-2 text-left font-body text-xs leading-snug transition-all hover:opacity-80"
                                            style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}
                                        >
                                            {q}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

function ExitConfirmModal({ onCancel, onConfirm }) {
    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-6"
            style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
            onClick={onCancel}
        >
            <div
                className="w-full max-w-sm rounded-2xl surface p-6 animate-fade-in"
                style={{ border: '1px solid var(--amber)' }}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="mb-3 flex items-center gap-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ backgroundColor: 'var(--amber-soft)' }}>
                        <AlertTriangle size={18} style={{ color: 'var(--amber)' }} />
                    </div>
                    <h2 className="font-display text-lg font-bold">Leave this session?</h2>
                </div>
                <p className="mb-5 font-body text-sm" style={{ color: 'var(--muted)' }}>
                    Your current conversation and analysis will be lost — nothing is saved once you leave.
                </p>
                <div className="flex items-center gap-2">
                    <button
                        onClick={onCancel}
                        className="flex-1 rounded-xl px-4 py-2.5 font-display text-sm font-semibold transition-all"
                        style={{ border: '1px solid var(--border)', color: 'var(--muted)' }}
                    >
                        Stay
                    </button>
                    <button
                        onClick={onConfirm}
                        className="flex-1 rounded-xl px-4 py-2.5 font-display text-sm font-semibold transition-colors"
                        style={{ backgroundColor: 'var(--amber)', color: 'var(--bg)' }}
                    >
                        Leave anyway
                    </button>
                </div>
            </div>
        </div>
    );
}

function MessageBubble({ msg, onFollowUpClick }) {
    const isUser = msg.role === 'user';

    if (isUser) {
        return (
            <div className="mb-4 flex justify-end animate-slide-up">
                <div className="max-w-[80%] rounded-2xl rounded-br-md px-4 py-2.5 font-body text-sm" style={{ background: 'var(--amber)', color: 'var(--bg)' }}>
                    {msg.text}
                </div>
            </div>
        );
    }

    return (
        <div className="mb-4 flex gap-3 animate-slide-up">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" style={{ background: 'var(--amber-soft)' }}>
                <Database size={14} style={{ color: 'var(--amber)' }} />
            </div>
            <div className="min-w-0 flex-1">
                <div
                    className="rounded-2xl rounded-tl-md px-4 py-3"
                    style={{
                        background: 'var(--surface)',
                        border: `1px solid ${msg.error ? 'var(--amber)' : 'var(--border)'}`,
                    }}
                >
                    <p className="font-body text-sm leading-relaxed" style={{ color: 'var(--text)' }}>
                        {renderMarkdown(msg.text)}
                    </p>
                    {msg.chart && (
                        // Horizontally scrollable instead of clipping/overlapping
                        // when a chart (esp. bar charts with many categories)
                        // is wider than the bubble. min-w-fit on the inner
                        // wrapper stops the chart being squeezed down to the
                        // bubble's width if it renders at a natural/intrinsic
                        // size rather than a percentage width.
                        <div className="mt-3 -mx-1 overflow-x-auto scroll-thin">
                            <div className="min-w-fit px-1">
                                <Chart spec={msg.chart} />
                            </div>
                        </div>
                    )}
                </div>

                {msg.followUpQuestions?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5 animate-fade-in">
                        {msg.followUpQuestions.map((q) => (
                            <button
                                key={q}
                                onClick={() => onFollowUpClick(q)}
                                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 font-body text-xs transition-all hover:opacity-80"
                                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--muted)' }}
                            >
                                {q}
                                <ArrowUpRight size={11} style={{ color: 'var(--teal)' }} />
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function renderMarkdown(text) {
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('`') && part.endsWith('`')) {
            return <code key={i} className="rounded px-1 font-mono text-xs" style={{ background: 'var(--bg)', color: 'var(--teal)' }}>{part.slice(1, -1)}</code>;
        }
        return <span key={i}>{part}</span>;
    });
}

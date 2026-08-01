import { useState, useRef, useEffect } from 'react';
import { Send, Download, Loader2, RotateCcw, Table2, Sparkles, Database } from 'lucide-react';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Chart } from '@/components/Chart';
import { analyzeQuery } from '@/lib/queryAnalyzer';
import { generateReport, downloadReport } from '@/lib/reportGenerator';

const SUGGESTED_QUESTIONS = [
    'How many rows are there?',
    'Show me the top 10 rows',
    'What columns are in the data?',
    'What is the distribution of categories?',
];

export function ChatScreen({ theme, onToggleTheme, onBack, tables }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [messages, loading]);

    const sendQuestion = async (question) => {
        const q = question.trim();
        if (!q || loading) return;

        const userMsg = { id: crypto.randomUUID(), role: 'user', text: q };
        setMessages((prev) => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const result = await analyzeQuery(q, tables);
            const assistantMsg = {
                id: crypto.randomUUID(),
                role: 'assistant',
                text: result.text,
                sql: result.sql,
                chart: result.chart,
                error: result.error,
            };
            setMessages((prev) => [...prev, assistantMsg]);
        } catch {
            setMessages((prev) => [
                ...prev,
                { id: crypto.randomUUID(), role: 'assistant', text: 'Something went wrong running that query. Try rephrasing.', error: true },
            ]);
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = () => {
        const report = generateReport(tables, messages);
        downloadReport(report);
    };

    const handleReset = () => {
        setMessages([]);
    };

    const hasMessages = messages.length > 0;

    return (
        <div className="flex h-screen flex-col">
            {/* Nav */}
            <nav className="flex shrink-0 items-center justify-between px-6 py-4 md:px-10">
                <div className="flex items-center gap-4">
                    <button onClick={onBack} className="font-mono text-xs uppercase tracking-wider transition-opacity hover:opacity-60" style={{ color: 'var(--muted)' }}>
                        ← New session
                    </button>
                    <span className="h-4 w-px" style={{ backgroundColor: 'var(--border)' }} />
                    <Logo onClick={onBack} />
                </div>
                <div className="flex items-center gap-3">
                    {hasMessages && (
                        <button
                            onClick={handleDownload}
                            className="inline-flex items-center gap-1.5 rounded-lg surface px-3 py-1.5 font-mono text-xs font-medium transition-all hover:opacity-80"
                        >
                            <Download size={13} style={{ color: 'var(--teal)' }} />
                            Report
                        </button>
                    )}
                    {hasMessages && (
                        <button
                            onClick={handleReset}
                            className="inline-flex items-center gap-1.5 rounded-lg surface px-3 py-1.5 font-mono text-xs font-medium transition-all hover:opacity-80"
                        >
                            <RotateCcw size={13} style={{ color: 'var(--muted)' }} />
                            Reset
                        </button>
                    )}
                    <ThemeToggle theme={theme} onToggle={onToggleTheme} />
                </div>
            </nav>

            {/* Tables context bar */}
            <div className="flex shrink-0 items-center gap-2 overflow-x-auto px-6 py-2 scroll-thin" style={{ borderBottom: '1px solid var(--border)' }}>
                <span className="font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Loaded:
                </span>
                {tables.map((t) => (
                    <span key={t.name} className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-xs" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                        <Table2 size={11} style={{ color: 'var(--teal)' }} />
                        {t.name}
                        <span style={{ color: 'var(--muted)' }}>· {t.rowCount.toLocaleString()}</span>
                    </span>
                ))}
            </div>

            {/* Chat area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-thin px-6 py-6">
                <div className="mx-auto max-w-3xl">
                    {!hasMessages && (
                        <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
                            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full" style={{ background: 'var(--amber-soft)' }}>
                                <Sparkles size={28} style={{ color: 'var(--amber)' }} />
                            </div>
                            <h2 className="font-display text-2xl font-bold">Ask anything about your data</h2>
                            <p className="mt-2 max-w-md font-body text-sm" style={{ color: 'var(--muted)' }}>
                                I'll translate your question into SQL, run it against your loaded tables, and return the answer with charts when useful.
                            </p>
                            <div className="mt-6 flex flex-wrap justify-center gap-2">
                                {SUGGESTED_QUESTIONS.map((q) => (
                                    <button
                                        key={q}
                                        onClick={() => sendQuestion(q)}
                                        className="rounded-lg surface px-3 py-2 font-body text-sm transition-all hover:opacity-80"
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {messages.map((msg) => (
                        <MessageBubble key={msg.id} msg={msg} />
                    ))}

                    {loading && (
                        <div className="flex items-center gap-2 py-3 animate-fade-in">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full" style={{ background: 'var(--amber-soft)' }}>
                                <Database size={14} style={{ color: 'var(--amber)' }} />
                            </div>
                            <div className="flex items-center gap-1.5">
                                <Loader2 size={14} className="animate-spin-slow" style={{ color: 'var(--muted)' }} />
                                <span className="font-mono text-xs" style={{ color: 'var(--muted)' }}>Running query...</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Input bar */}
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
    );
}

function MessageBubble({ msg }) {
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
                    {msg.sql && (
                        <div className="mt-3 rounded-lg p-3" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                            <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>SQL</p>
                            <pre className="overflow-x-auto scroll-thin font-mono text-xs leading-relaxed" style={{ color: 'var(--teal)' }}>
                                {msg.sql}
                            </pre>
                        </div>
                    )}
                    {msg.chart && <Chart spec={msg.chart} />}
                </div>
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
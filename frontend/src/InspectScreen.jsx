import { useState } from 'react';
import { FileSpreadsheet, Check, ArrowRight, ArrowLeft, Layers } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';

export function InspectScreen({ theme, onToggleTheme, onBack, files, onConfirm }) {
    // Default: select first sheet of each file (for single-sheet files, auto-select)
    const [selection, setSelection] = useState(() => {
        const set = new Set();
        for (const file of files) {
            if (file.sheets.length === 1) {
                set.add(sheetKey(file.fileName, file.sheets[0].sheetName));
            } else {
                // pre-select first sheet of multi-sheet files
                set.add(sheetKey(file.fileName, file.sheets[0].sheetName));
            }
        }
        return set;
    });

    const toggle = (fileName, sheetName) => {
        const key = sheetKey(fileName, sheetName);
        setSelection((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const handleConfirm = () => {
        const selected = [];
        for (const file of files) {
            for (const sheet of file.sheets) {
                if (selection.has(sheetKey(file.fileName, sheet.sheetName))) {
                    selected.push(sheet);
                }
            }
        }
        if (selected.length > 0) onConfirm(selected);
    };

    const selectedCount = selection.size;

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
                    <div className="mb-6 text-center animate-fade-in">
                        <span className="eyebrow">Step 2 — Select sheets</span>
                        <h1 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
                            Choose what to load
                        </h1>
                        <p className="mt-2 font-body text-sm" style={{ color: 'var(--muted)' }}>
                            {files.length === 1
                                ? files[0].sheets.length > 1
                                    ? 'This workbook has multiple sheets. Pick the ones you want to analyze.'
                                    : 'Review your file before loading.'
                                : 'Multiple files detected. Pick the sheets you want to analyze.'}
                        </p>
                    </div>

                    <div className="space-y-4">
                        {files.map((file) => (
                            <div key={file.fileName} className="rounded-2xl surface p-4 animate-fade-in">
                                <div className="mb-3 flex items-center gap-2">
                                    <FileSpreadsheet size={18} style={{ color: 'var(--teal)' }} />
                                    <span className="font-display text-sm font-semibold">{file.fileName}</span>
                                    {file.sheets.length > 1 && (
                                        <span className="ml-auto pill text-[10px]">
                                            <Layers size={11} />
                                            {file.sheets.length} sheets
                                        </span>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    {file.sheets.map((sheet) => {
                                        const key = sheetKey(file.fileName, sheet.sheetName);
                                        const isSelected = selection.has(key);
                                        const isEmpty = sheet.rows.length === 0;
                                        return (
                                            <button
                                                key={sheet.sheetName}
                                                onClick={() => toggle(file.fileName, sheet.sheetName)}
                                                disabled={isEmpty}
                                                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all"
                                                style={{
                                                    border: `1px solid ${isSelected ? 'var(--amber)' : 'var(--border)'}`,
                                                    background: isSelected ? 'var(--amber-soft)' : 'transparent',
                                                    opacity: isEmpty ? 0.4 : 1,
                                                    cursor: isEmpty ? 'not-allowed' : 'pointer',
                                                }}
                                            >
                                                <div
                                                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors"
                                                    style={{
                                                        borderColor: isSelected ? 'var(--amber)' : 'var(--border)',
                                                        backgroundColor: isSelected ? 'var(--amber)' : 'transparent',
                                                        color: 'var(--bg)',
                                                    }}
                                                >
                                                    {isSelected && <Check size={13} strokeWidth={3} />}
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <span className="font-body text-sm font-medium">{sheet.sheetName}</span>
                                                    {isEmpty ? (
                                                        <span className="ml-2 font-mono text-xs" style={{ color: 'var(--muted)' }}>empty</span>
                                                    ) : (
                                                        <span className="ml-2 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                                            {sheet.rows.length.toLocaleString()} rows · {sheet.columns.length} cols
                                                        </span>
                                                    )}
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>

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
                            onClick={handleConfirm}
                            disabled={selectedCount === 0}
                            className="btn-amber inline-flex items-center gap-2 rounded-xl px-6 py-3 font-display text-sm font-semibold disabled:opacity-50"
                        >
                            Load {selectedCount} {selectedCount === 1 ? 'sheet' : 'sheets'}
                            <ArrowRight size={16} strokeWidth={2.5} />
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

function sheetKey(fileName, sheetName) {
    return `${fileName}::${sheetName}`;
}
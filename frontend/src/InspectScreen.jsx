import { useState } from 'react';
import { FileSpreadsheet, ArrowRight, ArrowLeft, Layers } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';

export function InspectScreen({ theme, onToggleTheme, onBack, sessionId, files = [], onConfirm }) {
    // One sheet per file, not an array of sheets -- the backend rejects
    // more than one sheet/file selected in total (see upload.py's
    // _load_selected_dataframe: "Analyzing multiple sheets or files at
    // once isn't supported yet"). Defaults to the workbook's first sheet
    // so Continue is usable immediately without making the user pick.
    const [selection, setSelection] = useState(() => {
        const map = {};
        for (const file of files) {
            if (file.type === 'excel' && file.sheets.length > 0) {
                map[file.filename] = file.sheets[0];
            }
        }
        return map;
    });

    const selectSheet = (filename, sheet) => {
        setSelection((prev) => ({ ...prev, [filename]: sheet }));
    };

    const selectedCount = files.reduce((sum, f) => {
        if (f.type === 'csv') return sum + 1;
        return sum + (selection[f.filename] ? 1 : 0);
    }, 0);

    // No network call here -- ConfirmScreen owns preview/confirm requests.
    // This screen's only job is picking a sheet and handing off the selection.
    const handleContinue = () => {
        const selections = files.map((f) => ({
            filename: f.filename,
            sheets: f.type === 'excel' ? (selection[f.filename] ? [selection[f.filename]] : []) : null,
        }));
        onConfirm({ sessionId, selections });
    };

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
                        <span className="eyebrow">Step 2 — Select a sheet</span>
                        <h1 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
                            Choose what to load
                        </h1>
                        <p className="mt-2 font-body text-sm" style={{ color: 'var(--muted)' }}>
                            {files.some((f) => f.type === 'excel')
                                ? 'Pick the one sheet you want to analyze from each workbook.'
                                : 'Review your file before loading.'}
                        </p>
                    </div>

                    <div className="space-y-4">
                        {files.map((file) => (
                            <div key={file.filename} className="rounded-2xl surface p-4 animate-fade-in">
                                <div className="mb-3 flex items-center gap-2">
                                    <FileSpreadsheet size={18} style={{ color: 'var(--teal)' }} />
                                    <span className="font-display text-sm font-semibold">{file.filename}</span>
                                    {file.type === 'excel' && (
                                        <span className="ml-auto pill text-[10px]">
                                            <Layers size={11} />
                                            {file.sheets.length} sheets
                                        </span>
                                    )}
                                </div>

                                {file.type === 'csv' ? (
                                    <p className="text-sm" style={{ color: 'var(--muted)' }}>
                                        Single table — loaded automatically.
                                    </p>
                                ) : (
                                    <div className="space-y-2" role="radiogroup" aria-label={`Sheet in ${file.filename}`}>
                                        {file.sheets.map((sheet) => {
                                            const isSelected = selection[file.filename] === sheet;
                                            return (
                                                <button
                                                    key={sheet}
                                                    role="radio"
                                                    aria-checked={isSelected}
                                                    onClick={() => selectSheet(file.filename, sheet)}
                                                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all"
                                                    style={{
                                                        border: `1px solid ${isSelected ? 'var(--amber)' : 'var(--border)'}`,
                                                        background: isSelected ? 'var(--amber-soft)' : 'transparent',
                                                    }}
                                                >
                                                    <div
                                                        className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors"
                                                        style={{
                                                            borderColor: isSelected ? 'var(--amber)' : 'var(--border)',
                                                        }}
                                                    >
                                                        {isSelected && (
                                                            <div
                                                                className="h-2.5 w-2.5 rounded-full"
                                                                style={{ backgroundColor: 'var(--amber)' }}
                                                            />
                                                        )}
                                                    </div>
                                                    <span className="font-body text-sm font-medium">{sheet}</span>
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

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
                            onClick={handleContinue}
                            disabled={selectedCount === 0}
                            className="btn-amber inline-flex items-center gap-2 rounded-xl px-6 py-3 font-display text-sm font-semibold disabled:opacity-50"
                        >
                            Continue
                            <ArrowRight size={16} strokeWidth={2.5} />
                        </button>
                    </div>
                </div>
            </main>

            <footer className="px-6 py-5 text-center">
                <p className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                    Your file is deleted the moment you leave — or automatically after a short period of inactivity.
                </p>
            </footer>
        </div>
    );
}
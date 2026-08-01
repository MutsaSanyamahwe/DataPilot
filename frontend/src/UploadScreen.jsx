import { useState, useRef, useCallback } from 'react';
import { UploadCloud, FileSpreadsheet, X, ArrowRight, Loader2 } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { parseFile } from './lib/fileParser';

export function UploadScreen({ theme, onToggleTheme, onBack, onFilesParsed }) {
    const [isDragging, setIsDragging] = useState(false);
    const [parsing, setParsing] = useState(false);
    const [error, setError] = useState(null);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const inputRef = useRef(null);

    const handleFiles = useCallback(async (fileList) => {
        if (!fileList || fileList.length === 0) return;
        const valid = Array.from(fileList).filter((f) => {
            const ext = f.name.split('.').pop()?.toLowerCase();
            return ext === 'csv' || ext === 'xlsx' || ext === 'xls' || ext === 'tsv';
        });
        if (valid.length === 0) {
            setError('Please upload CSV or Excel files (.csv, .xlsx, .xls).');
            return;
        }
        setError(null);
        setSelectedFiles(valid);
    }, []);

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
    };

    const handleProceed = async () => {
        if (selectedFiles.length === 0) return;
        setParsing(true);
        setError(null);
        try {
            const parsed = [];
            for (const file of selectedFiles) {
                const result = await parseFile(file);
                parsed.push(result);
            }
            onFilesParsed(parsed);
        } catch {
            setError('Could not read those files. Make sure they are valid CSV or Excel files.');
        } finally {
            setParsing(false);
        }
    };

    const removeFile = (idx) => {
        setSelectedFiles((prev) => prev.filter((_, i) => i !== idx));
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
                        <span className="eyebrow">Step 1 — Upload</span>
                        <h1 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
                            Drop your data here
                        </h1>
                        <p className="mt-2 font-body text-sm" style={{ color: 'var(--muted)' }}>
                            CSV, XLSX, or XLS files. You can add multiple files at once.
                        </p>
                    </div>

                    {/* Dropzone */}
                    <div
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => inputRef.current?.click()}
                        className="relative cursor-pointer rounded-2xl surface transition-all duration-300 animate-fade-in"
                        style={{
                            borderColor: isDragging ? 'var(--amber)' : 'var(--border)',
                            borderWidth: '2px',
                            borderStyle: isDragging ? 'solid' : 'dashed',
                            background: isDragging ? 'var(--amber-soft)' : 'var(--surface)',
                        }}
                    >
                        <input
                            ref={inputRef}
                            type="file"
                            multiple
                            accept=".csv,.xlsx,.xls,.tsv"
                            className="hidden"
                            onChange={(e) => handleFiles(e.target.files)}
                        />
                        <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
                            <div
                                className="mb-4 flex h-16 w-16 items-center justify-center rounded-full transition-transform duration-300"
                                style={{
                                    backgroundColor: 'var(--amber-soft)',
                                    color: 'var(--amber)',
                                    transform: isDragging ? 'scale(1.1)' : 'scale(1)',
                                }}
                            >
                                <UploadCloud size={28} strokeWidth={1.75} />
                            </div>
                            <p className="font-display text-lg font-semibold">
                                {isDragging ? 'Release to upload' : 'Drag & drop files here'}
                            </p>
                            <p className="mt-1 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                or click to browse
                            </p>
                        </div>
                    </div>

                    {/* Error */}
                    {error && (
                        <p className="mt-4 text-center font-mono text-xs" style={{ color: 'var(--amber)' }}>
                            {error}
                        </p>
                    )}

                    {/* Selected files */}
                    {selectedFiles.length > 0 && (
                        <div className="mt-5 space-y-2 animate-slide-up">
                            {selectedFiles.map((file, idx) => (
                                <div
                                    key={idx}
                                    className="flex items-center justify-between rounded-lg surface px-4 py-3 animate-fade-in"
                                >
                                    <div className="flex items-center gap-3">
                                        <FileSpreadsheet size={18} style={{ color: 'var(--teal)' }} />
                                        <div>
                                            <p className="font-body text-sm font-medium">{file.name}</p>
                                            <p className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                                {(file.size / 1024).toFixed(1)} KB
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                                        className="rounded-lg p-1.5 transition-colors hover:opacity-70"
                                        style={{ color: 'var(--muted)' }}
                                    >
                                        <X size={16} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Proceed button */}
                    {selectedFiles.length > 0 && (
                        <div className="mt-6 flex justify-center animate-fade-in">
                            <button
                                onClick={handleProceed}
                                disabled={parsing}
                                className="btn-amber inline-flex items-center gap-2 rounded-xl px-6 py-3 font-display text-sm font-semibold disabled:opacity-60"
                            >
                                {parsing ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin-slow" />
                                        Parsing files...
                                    </>
                                ) : (
                                    <>
                                        Continue
                                        <ArrowRight size={16} strokeWidth={2.5} />
                                    </>
                                )}
                            </button>
                        </div>
                    )}
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
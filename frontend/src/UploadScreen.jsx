import { useState, useRef, useCallback } from 'react';
import { UploadCloud, FileSpreadsheet, X, ArrowRight, Loader2 } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';

const API_BASE = 'https://datapilot-opfy.onrender.com';

export function UploadScreen({ theme, onToggleTheme, onBack, onFilesParsed }) {
    const [isDragging, setIsDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    // Single file, not an array -- the backend only supports one
    // dataframe per session (see upload.py's module docstring: selecting
    // more than one sheet/file is rejected at /upload/confirm). Letting
    // someone pick several here just means they find that out later,
    // after they've already gone through Inspect/Confirm -- better to
    // make it impossible to pick more than one in the first place.
    const [selectedFile, setSelectedFile] = useState(null);
    const inputRef = useRef(null);

    const handleFiles = useCallback((fileList) => {
        if (!fileList || fileList.length === 0) return;
        const valid = Array.from(fileList).filter((f) => {
            const ext = f.name.split('.').pop()?.toLowerCase();
            return ext === 'csv' || ext === 'xlsx' || ext === 'xls';
        });
        if (valid.length === 0) {
            setError('Please upload a CSV or Excel file (.csv, .xlsx, .xls).');
            return;
        }
        if (fileList.length > 1) {
            // Someone dragged/selected several at once -- take the first
            // valid one and say so, rather than silently discarding the
            // rest or letting a multi-file selection through.
            setError(`Only one file can be analyzed at a time — using "${valid[0].name}".`);
        } else {
            setError(null);
        }
        setSelectedFile(valid[0]);
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
        if (!selectedFile) return;
        setUploading(true);
        setError(null);

        const formData = new FormData();
        // Still appended under "files" -- the backend's /upload/inspect
        // accepts a list (List[UploadFile]) even though we only ever send
        // one now; no backend change needed for this restriction.
        formData.append('files', selectedFile);

        try {
            const res = await fetch(`${API_BASE}/upload/inspect`, {
                method: 'POST',
                body: formData,
            });
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail || `Server error: ${res.status}`);
            }
            const data = await res.json();
            onFilesParsed(data); // { session_id, files }
        } catch (err) {
            setError(err.message || 'Could not upload that file. Is the backend running?');
        } finally {
            setUploading(false);
        }
    };

    const clearFile = () => {
        setSelectedFile(null);
        setError(null);
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
                            CSV or Excel file — one file per session.
                        </p>
                    </div>

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
                            accept=".csv,.xlsx,.xls"
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
                                {isDragging ? 'Release to upload' : 'Drag & drop a file here'}
                            </p>
                            <p className="mt-1 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                or click to browse
                            </p>
                        </div>
                    </div>

                    {error && (
                        <p className="mt-4 text-center font-mono text-xs" style={{ color: 'var(--amber)' }}>
                            {error}
                        </p>
                    )}

                    {selectedFile && (
                        <div className="mt-5 animate-slide-up">
                            <div className="flex items-center justify-between rounded-lg surface px-4 py-3 animate-fade-in">
                                <div className="flex items-center gap-3">
                                    <FileSpreadsheet size={18} style={{ color: 'var(--teal)' }} />
                                    <div>
                                        <p className="font-body text-sm font-medium">{selectedFile.name}</p>
                                        <p className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                                            {(selectedFile.size / 1024).toFixed(1)} KB
                                        </p>
                                    </div>
                                </div>
                                <button
                                    onClick={(e) => { e.stopPropagation(); clearFile(); }}
                                    className="rounded-lg p-1.5 transition-colors hover:opacity-70"
                                    style={{ color: 'var(--muted)' }}
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        </div>
                    )}

                    {selectedFile && (
                        <div className="mt-6 flex justify-center animate-fade-in">
                            <button
                                onClick={handleProceed}
                                disabled={uploading}
                                className="btn-amber inline-flex items-center gap-2 rounded-xl px-6 py-3 font-display text-sm font-semibold disabled:opacity-60"
                            >
                                {uploading ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin-slow" />
                                        Uploading...
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
                    Your file is deleted the moment you leave — or automatically after a short period of inactivity.
                </p>
            </footer>
        </div>
    );
}

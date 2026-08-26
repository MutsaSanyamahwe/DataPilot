import { useState } from 'react'

const API_BASE = 'https://datapilot-opfy.onrender.com'

function UploadForm() {
  const [files, setFiles] = useState([])
  const [inspectData, setInspectData] = useState(null)
  const [sheetSelections, setSheetSelections] = useState({})
  const [tables, setTables] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files))
    setInspectData(null)
    setTables(null)
    setError(null)
  }

  const handleInspect = async () => {
    if (files.length === 0) return
    setLoading(true)
    setError(null)

    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))

    try {
      const res = await fetch(`${API_BASE}/upload/inspect`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()
      setInspectData(data)

      const defaults = {}
      data.files.forEach((f) => {
        if (f.type === 'excel') {
          defaults[f.filename] = [...f.sheets]
        }
      })
      setSheetSelections(defaults)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleSheet = (filename, sheet) => {
    setSheetSelections((prev) => {
      const current = prev[filename] || []
      const updated = current.includes(sheet)
        ? current.filter((s) => s !== sheet)
        : [...current, sheet]
      return { ...prev, [filename]: updated }
    })
  }

  const handleConfirm = async () => {
    if (!inspectData) return
    setLoading(true)
    setError(null)

    const selections = inspectData.files.map((f) => ({
      filename: f.filename,
      sheets: f.type === 'excel' ? sheetSelections[f.filename] : null,
    }))

    try {
      const res = await fetch(`${API_BASE}/upload/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: inspectData.session_id,
          selections,
        }),
      })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()
      setTables(data.tables)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h2 className="font-display font-semibold text-2xl">Upload your data</h2>
        <p className="text-sm mt-1" style={{ color: 'var(--ink-muted)' }}>
          CSV or Excel files, multiple at once.
        </p>
      </div>

      <label
        className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-10 cursor-pointer transition-colors"
        style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}
      >
        <span className="font-mono text-sm" style={{ color: 'var(--ink-muted)' }}>
          {files.length > 0
            ? `${files.length} file${files.length > 1 ? 's' : ''} selected`
            : 'Click to choose files'}
        </span>
        <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
          .csv, .xlsx, .xls
        </span>
        <input
          type="file"
          multiple
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
          className="hidden"
        />
      </label>

      {files.length > 0 && !inspectData && (
        <button
          onClick={handleInspect}
          disabled={loading}
          className="font-display font-medium px-5 py-2.5 rounded-lg transition-opacity disabled:opacity-50"
          style={{ background: 'var(--amber)', color: 'var(--bg)' }}
        >
          {loading ? 'Scanning files…' : 'Continue'}
        </button>
      )}

      {inspectData && !tables && (
        <div className="space-y-4">
          {inspectData.files.map((f) => (
            <div
              key={f.filename}
              className="rounded-xl border p-4"
              style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
            >
              <p className="font-medium">{f.filename}</p>
              {f.type === 'csv' ? (
                <p className="text-sm mt-1" style={{ color: 'var(--ink-muted)' }}>
                  Single table (CSV)
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  {f.sheets.map((sheet) => (
                    <label key={sheet} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={sheetSelections[f.filename]?.includes(sheet) || false}
                        onChange={() => toggleSheet(f.filename, sheet)}
                        style={{ accentColor: 'var(--teal)' }}
                      />
                      <span style={{ color: 'var(--ink-muted)' }}>{sheet}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}

          <button
            onClick={handleConfirm}
            disabled={loading}
            className="font-display font-medium px-5 py-2.5 rounded-lg transition-opacity disabled:opacity-50"
            style={{ background: 'var(--teal)', color: 'var(--bg)' }}
          >
            {loading ? 'Loading data…' : 'Load selected data'}
          </button>
        </div>
      )}

      {tables && (
        <div
          className="rounded-xl border p-5 space-y-3"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <p className="font-display font-medium" style={{ color: 'var(--teal)' }}>
            Data loaded
          </p>
          <div className="space-y-2">
            {tables.map((t) => (
              <div key={t.table_name} className="text-sm">
                <span className="font-mono" style={{ color: 'var(--amber)' }}>
                  {t.table_name}
                </span>
                <span style={{ color: 'var(--ink-muted)' }}>
                  {' '}— {t.rows} rows · {t.columns.join(', ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm" style={{ color: '#E5484D' }}>
          {error}
        </p>
      )}
    </div>
  )
}

export default UploadForm

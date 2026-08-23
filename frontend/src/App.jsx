import { useState, useEffect } from 'react'
import { Landing as LandingPage } from './LandingPage'
import { UploadScreen } from './UploadScreen'
import { InspectScreen } from './InspectScreen'
import { ConfirmScreen } from './ConfirmScreen'
import { ChatScreen } from './ChatScreen'

function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('datapilot-theme') || 'dark'
  )
  const [view, setView] = useState('landing')

  const [sessionId, setSessionId] = useState(null)
  const [inspectFiles, setInspectFiles] = useState([])
  const [selections, setSelections] = useState([])
  const [loadedTables, setLoadedTables] = useState([])
  // Type-aware column info (name/dtype/sample_values) from /upload/confirm --
  // used by ChatScreen's "explore your data" sidebar to generate suggested
  // questions that actually match each column's real type, instead of
  // guessing from bare column names.
  const [columnsDetail, setColumnsDetail] = useState([])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('datapilot-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  const goTo = (nextView) => () => setView(nextView)

  const resetSession = () => {
    setSessionId(null)
    setInspectFiles([])
    setSelections([])
    setLoadedTables([])
    setColumnsDetail([])
    setView('landing')
  }

  if (view === 'landing') {
    return <LandingPage theme={theme} onToggleTheme={toggleTheme} onGetStarted={goTo('upload')} />
  }

  if (view === 'upload') {
    return (
      <UploadScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onBack={goTo('landing')}
        onFilesParsed={(data) => {
          setSessionId(data.session_id)
          setInspectFiles(data.files)
          setView('inspect')
        }}
      />
    )
  }

  if (view === 'inspect') {
    return (
      <InspectScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onBack={goTo('upload')}
        sessionId={sessionId}
        files={inspectFiles}
        // InspectScreen no longer calls the backend itself -- it just hands
        // off { sessionId, selections }. ConfirmScreen owns the actual
        // /upload/preview + /upload/confirm calls.
        onConfirm={({ sessionId: sid, selections: sel }) => {
          setSessionId(sid)
          setSelections(sel)
          setView('confirm')
        }}
      />
    )
  }

  if (view === 'confirm') {
    return (
      <ConfirmScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onBack={goTo('inspect')}
        sessionId={sessionId}
        selections={selections}
        // ConfirmScreen calls /upload/confirm itself and passes the real
        // response here once the user commits -- that's where "tables"
        // and "columns_detail" actually come from now.
        onProceed={(data) => {
          setLoadedTables(data.tables)
          setColumnsDetail(data.columns_detail || [])
          setView('chat')
        }}
      />
    )
  }

  if (view === 'chat') {
    return (
      <ChatScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onBack={resetSession}
        sessionId={sessionId}
        tables={loadedTables}
        columnsDetail={columnsDetail}
      />
    )
  }

  return null
}

export default App
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
  const [loadedTables, setLoadedTables] = useState([])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('datapilot-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  const goTo = (nextView) => () => setView(nextView)

  const resetSession = () => {
    setSessionId(null)
    setInspectFiles([])
    setLoadedTables([])
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
        onConfirm={(data) => {
          setLoadedTables(data.tables)
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
        tables={loadedTables}
        onProceed={goTo('chat')}
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
      />
    )
  }

  return null
}

export default App
import { useState, useEffect } from 'react'
import LandingPage from './LandingPage'
import { UploadScreen } from './UploadScreen'
import { InspectScreen } from './InspectScreen'
import { ConfirmScreen } from './ConfirmScreen'
import { ChatScreen } from './ChatScreen'

function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('datapilot-theme') || 'dark'
  )
  // 'landing' | 'upload' | 'inspect' | 'confirm' | 'chat'
  const [view, setView] = useState('landing')

  const [rawFiles, setRawFiles] = useState([])       // File objects from UploadScreen
  const [parsedFiles, setParsedFiles] = useState([])  // parsed file+sheet data → InspectScreen
  const [loadedTables, setLoadedTables] = useState([]) // confirmed tables → ConfirmScreen / ChatScreen

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('datapilot-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  const goTo = (nextView) => () => setView(nextView)

  if (view === 'landing') {
    return (
      <LandingPage
        theme={theme}
        onToggleTheme={toggleTheme}
        onGetStarted={goTo('upload')}
      />
    )
  }

  if (view === 'upload') {
    return (
      <UploadScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onBack={goTo('landing')}
        onFilesParsed={(parsed) => {
          setParsedFiles(parsed)
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
        files={parsedFiles}
        onConfirm={(selectedSheets) => {
          setLoadedTables(selectedSheets)
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
        onBack={() => {
          setRawFiles([])
          setParsedFiles([])
          setLoadedTables([])
          setView('landing')
        }}
        tables={loadedTables}
      />
    )
  }

  return null
}

export default App
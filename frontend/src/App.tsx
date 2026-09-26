import { useEffect, useState } from 'react'
import { BrowserRouter, HashRouter, Route, Routes } from 'react-router-dom'
import { STATIC } from './api/client'
import { editorMode, githubEnabled, setEditorMode } from './lib/stories'
import { Home } from './pages/Home'
import { SeasonArcPage } from './pages/SeasonArcPage'
import { TrackDetail } from './pages/TrackDetail'
import { StoreProvider } from './state/store'

// GitHub Pages has no server-side routing, so the static build keeps routes in the URL hash.
const Router = STATIC ? HashRouter : BrowserRouter

function EditorBadge() {
  const [on, setOn] = useState(editorMode)
  useEffect(() => {
    const sync = () => setOn(editorMode())
    window.addEventListener('hashchange', sync)
    window.addEventListener('popstate', sync)
    return () => { window.removeEventListener('hashchange', sync); window.removeEventListener('popstate', sync) }
  }, [])
  if (!on || !githubEnabled) return null
  return (
    <div className="fixed bottom-3 right-3 z-50 card px-3 py-1.5 text-xs flex items-center gap-2" style={{ borderColor: 'var(--accent)' }}>
      <span className="font-semibold">Editor mode</span>
      <span className="faint">Edit links open GitHub</span>
      <button className="btn" onClick={() => { setEditorMode(false); setOn(false); window.location.reload() }}>Exit</button>
    </div>
  )
}

export default function App() {
  return (
    <StoreProvider>
      <EditorBadge />
      <Router basename={STATIC ? undefined : import.meta.env.BASE_URL}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/race/:eventId" element={<TrackDetail />} />
          <Route path="/season/:year" element={<SeasonArcPage />} />
        </Routes>
      </Router>
    </StoreProvider>
  )
}

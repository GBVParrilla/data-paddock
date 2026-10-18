import { useEffect, useState } from 'react'
import { BrowserRouter, HashRouter, Route, Routes, useLocation } from 'react-router-dom'
import { STATIC } from './api/client'
import { Boundary, NotFound } from './components/Boundary'
import { Shell } from './components/Shell'
import { editorMode, githubEnabled, setEditorMode } from './lib/stories'
import { Home } from './pages/Home'
import { RaceWeekend } from './pages/RaceWeekend'
import { SeasonPage } from './pages/SeasonPage'
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
    <div className="fixed bottom-4 right-4 z-50 panel px-3 py-2 text-[12px] flex items-center gap-3">
      <span className="dot" style={{ background: 'var(--accent)' }} />
      <span>Editor mode</span>
      <button className="btn-ghost" onClick={() => { setEditorMode(false); setOn(false); window.location.reload() }}>Exit</button>
    </div>
  )
}

/** A crash inside one route never blanks the app; navigating away clears it. */
function PageBoundary({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  return <Boundary key={pathname} label="This page" page>{children}</Boundary>
}

function ScrollTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <StoreProvider>
      <EditorBadge />
      <Router basename={STATIC ? undefined : import.meta.env.BASE_URL}>
        <ScrollTop />
        <Shell>
          <PageBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/races" element={<Home />} />
              <Route path="/race/:eventId" element={<RaceWeekend />} />
              <Route path="/season/:year" element={<SeasonPage />} />
              <Route path="/season/" element={<Home />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </PageBoundary>
        </Shell>
      </Router>
    </StoreProvider>
  )
}

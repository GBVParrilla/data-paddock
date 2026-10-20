import { lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { Boundary, NotFound } from './components/Boundary'
import { Shell } from './components/Shell'
import { editorMode, githubEnabled, setEditorMode } from './lib/stories'
import { Home } from './pages/Home'

// route-level code splitting: the home page doesn't pay for the charts (REVIEW #25)
const RaceWeekend = lazy(() => import('./pages/RaceWeekend').then((m) => ({ default: m.RaceWeekend })))
const SeasonPage = lazy(() => import('./pages/SeasonPage').then((m) => ({ default: m.SeasonPage })))
const RacesPage = lazy(() => import('./pages/RacesPage').then((m) => ({ default: m.RacesPage })))
const MethodsPage = lazy(() => import('./pages/MethodsPage').then((m) => ({ default: m.MethodsPage })))
import { ModeProvider } from './state/mode'
import { StoreProvider } from './state/store'

// Path routes. On GitHub Pages every shareable page is prerendered as its own HTML shell and
// 404.html covers the rest (docs/adr/0001-path-routing-and-prerendered-shells.md).
const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '') || undefined

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
      <BrowserRouter basename={BASENAME}>
        <ScrollTop />
        <ModeProvider>
          <Shell>
            <PageBoundary>
              <Suspense fallback={<div className="wrap pt-10" aria-busy="true"><p className="label">Loading the page…</p><div className="skeleton h-10 w-72 mt-3" /><div className="skeleton h-64 mt-6" /></div>}>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/races" element={<RacesPage />} />
                <Route path="/race/:eventId" element={<RaceWeekend />} />
                <Route path="/race/:eventId/driver/:driverRef" element={<RaceWeekend />} />
                <Route path="/season/:year" element={<SeasonPage />} />
                <Route path="/season/" element={<Home />} />
                <Route path="/methods" element={<MethodsPage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
              </Suspense>
            </PageBoundary>
          </Shell>
        </ModeProvider>
      </BrowserRouter>
    </StoreProvider>
  )
}

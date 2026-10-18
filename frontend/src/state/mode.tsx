import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

/** Essential: the verdict-first story. Expert: the same story with its data inline and More detail open (decision D5). */
export type Mode = 'essential' | 'expert'

const KEY = 'data-paddock:mode'
function stored(): Mode {
  try {
    return localStorage.getItem(KEY) === 'expert' ? 'expert' : 'essential'
  } catch {
    return 'essential' // storage blocked (private window, embedded preview): fall back quietly
  }
}
function remember(m: Mode) {
  try {
    localStorage.setItem(KEY, m)
  } catch {
    /* not remembered; the page still works */
  }
}

interface ModeState { mode: Mode; expert: boolean; setMode: (m: Mode) => void }
const Ctx = createContext<ModeState | null>(null)

export function ModeProvider({ children }: { children: ReactNode }) {
  const [search, setSearch] = useSearchParams()
  const fromUrl = search.get('mode')
  const linked: Mode | null = fromUrl === 'expert' || fromUrl === 'essential' ? fromUrl : null
  const [chosen, setChosen] = useState<Mode>(stored)
  // a shared ?mode= link wins, and becomes the reader's choice
  useEffect(() => {
    if (linked) remember(linked)
  }, [linked])
  const mode = linked ?? chosen
  const setMode = useCallback((m: Mode) => {
    setChosen(m)
    remember(m)
    setSearch((p) => { p.delete('mode'); return p }, { replace: true })
  }, [setSearch])
  const value = useMemo(() => ({ mode, expert: mode === 'expert', setMode }), [mode, setMode])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useMode(): ModeState {
  const m = useContext(Ctx)
  if (!m) throw new Error('useMode outside ModeProvider')
  return m
}

/** The header switch: two states, one tap. */
export function ModeSwitch() {
  const { mode, setMode } = useMode()
  return (
    <div className="seg sm" role="radiogroup" aria-label="Detail level">
      {(['essential', 'expert'] as const).map((m) => (
        <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}>
          {m === 'essential' ? 'Essential' : 'Expert'}
        </button>
      ))}
    </div>
  )
}

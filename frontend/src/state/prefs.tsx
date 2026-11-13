import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'

/**
 * The reader's own settings, kept in this browser only: the driver they follow (home puts them first) and
 * spoiler-free mode (results from the latest rounds stay hidden until revealed, for fans who watch delayed).
 */
export type Followed = { id: number; ref: string; name: string }
type Spoilers = { from: number; revealed: number[] } | null

const FOLLOW = 'data-paddock:follow'
const SPOILERS = 'data-paddock:spoilers'

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback // storage blocked or corrupt: the default, quietly
  }
}
function save(key: string, value: unknown) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* not remembered; the page still works */
  }
}

interface PrefsState {
  followed: Followed | null
  setFollowed: (d: Followed | null) => void
  spoilerFree: boolean
  /** turning it on hides the latest round and every round after it; older rounds count as seen */
  setSpoilerFree: (on: boolean) => void
  hidden: (round: number | null | undefined) => boolean
  reveal: (rounds: number[]) => void
}
const Ctx = createContext<PrefsState | null>(null)

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [followed, setF] = useState<Followed | null>(() => load(FOLLOW, null))
  const [spoilers, setS] = useState<Spoilers>(() => load(SPOILERS, null))
  const setFollowed = useCallback((d: Followed | null) => { setF(d); save(FOLLOW, d) }, [])
  const update = useCallback((s: Spoilers) => { setS(s); save(SPOILERS, s) }, [])
  const setSpoilerFree = useCallback((on: boolean) => {
    if (!on) { update(null); return }
    update({ from: 1, revealed: [] }) // everything hidden until the latest round is known, never a flash of results
    api.meta().then((m) => update({ from: m.last_round ?? 1, revealed: [] }), () => {})
  }, [update])
  const hidden = useCallback((round: number | null | undefined) => !!spoilers && round != null && round >= spoilers.from && !spoilers.revealed.includes(round), [spoilers])
  const reveal = useCallback((rounds: number[]) => {
    if (spoilers) update({ ...spoilers, revealed: [...new Set([...spoilers.revealed, ...rounds])] })
  }, [spoilers, update])
  const value = useMemo(() => ({ followed, setFollowed, spoilerFree: !!spoilers, setSpoilerFree, hidden, reveal }), [followed, setFollowed, spoilers, setSpoilerFree, hidden, reveal])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePrefs(): PrefsState {
  const p = useContext(Ctx)
  if (!p) throw new Error('usePrefs outside PrefsProvider')
  return p
}

/** The header switch. */
export function SpoilerSwitch() {
  const { spoilerFree, setSpoilerFree } = usePrefs()
  return (
    <button type="button" className="btn-ghost text-[12.5px] flex items-center gap-1.5" aria-pressed={spoilerFree} onClick={() => setSpoilerFree(!spoilerFree)}
      title={spoilerFree ? 'Spoiler-free: the latest results are hidden until you reveal them' : 'Hide the latest results, for watching later'}>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8s-2.4 4.5-6.5 4.5S1.5 8 1.5 8z" /><circle cx="8" cy="8" r="2" />
        {spoilerFree && <path d="M2.5 13.5l11-11" />}
      </svg>
      <span className="hidden sm:inline">{spoilerFree ? 'Spoiler-free on' : 'Spoiler-free'}</span>
      <span className="sr-only sm:hidden">Spoiler-free mode</span>
    </button>
  )
}

/** In place of a hidden result: what is hidden, and the one button that shows it. */
export function SpoilerGate({ rounds, what, className = '' }: { rounds: number[]; what: string; className?: string }) {
  const { reveal } = usePrefs()
  return (
    <div className={`flex flex-wrap items-center gap-3 text-[13px] ${className}`} data-spoiler-gate>
      <span className="t2">{what}</span>
      <button type="button" className="btn" onClick={() => reveal(rounds)}>Show the result{rounds.length > 1 ? 's' : ''}</button>
    </div>
  )
}

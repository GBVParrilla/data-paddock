import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

interface State { year: number | null; eventId: number | null; sessionId: number | null; driverIds: number[] }
interface Store extends State {
  setYear: (y: number | null) => void
  setEvent: (id: number | null) => void
  /** `presentDrivers`: ids that have data in the new session; drivers not present are dropped. */
  setSession: (id: number | null, presentDrivers?: Set<number>) => void
  toggleDriver: (id: number) => void
  clearDrivers: () => void
}

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ year: null, eventId: null, sessionId: null, driverIds: [] })
  const setYear = useCallback((year: number | null) => setState((s) => (s.year === year ? s : { year, eventId: null, sessionId: null, driverIds: [] })), [])
  const setEvent = useCallback((eventId: number | null) => setState((s) => (s.eventId === eventId ? s : { ...s, eventId, sessionId: null, driverIds: [] })), [])
  const setSession = useCallback(
    (sessionId: number | null, present?: Set<number>) =>
      setState((s) => ({ ...s, sessionId, driverIds: present ? s.driverIds.filter((d) => present.has(d)) : s.driverIds })),
    [],
  )
  const toggleDriver = useCallback(
    (id: number) =>
      setState((s) => {
        // clicking a selected driver again deselects them
        if (s.driverIds.includes(id)) return { ...s, driverIds: s.driverIds.filter((d) => d !== id) }
        // 0 -> 1 -> 2 (comparison). Picking a third distinct driver starts a fresh selection with
        // just that driver, rather than bumping one of the existing two.
        const next = s.driverIds.length < 2 ? [...s.driverIds, id] : [id]
        return { ...s, driverIds: next }
      }),
    [],
  )
  const clearDrivers = useCallback(() => setState((s) => ({ ...s, driverIds: [] })), [])
  const value = useMemo(() => ({ ...state, setYear, setEvent, setSession, toggleDriver, clearDrivers }), [state, setYear, setEvent, setSession, toggleDriver, clearDrivers])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useStore(): Store {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore outside StoreProvider')
  return s
}

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

/** `driverIds` holds at most one driver: a tap always means "show me this driver" (REVIEW_ROUND3 D8, #50).
 * `vsId` is who they're compared with in their panel; null means their teammate that weekend. */
interface State { year: number | null; eventId: number | null; sessionId: number | null; driverIds: number[]; vsId: number | null }
interface Store extends State {
  setYear: (y: number | null) => void
  setEvent: (id: number | null) => void
  /** `presentDrivers`: ids that have data in the new session; drivers not present are dropped. */
  setSession: (id: number | null, presentDrivers?: Set<number>) => void
  /** Select one driver, replacing any other; selecting the selected driver again clears the selection. */
  selectDriver: (id: number, vs?: number | null) => void
  setVs: (id: number | null) => void
  clearDrivers: () => void
}

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ year: null, eventId: null, sessionId: null, driverIds: [], vsId: null })
  const setYear = useCallback((year: number | null) => setState((s) => (s.year === year ? s : { year, eventId: null, sessionId: null, driverIds: [], vsId: null })), [])
  const setEvent = useCallback((eventId: number | null) => setState((s) => (s.eventId === eventId ? s : { ...s, eventId, sessionId: null, driverIds: [], vsId: null })), [])
  const setSession = useCallback(
    (sessionId: number | null, present?: Set<number>) =>
      setState((s) => {
        const driverIds = present ? s.driverIds.filter((d) => present.has(d)) : s.driverIds
        const vsId = present && s.vsId !== null && !present.has(s.vsId) ? null : s.vsId
        return { ...s, sessionId, driverIds, vsId: driverIds.length ? vsId : null }
      }),
    [],
  )
  const selectDriver = useCallback(
    (id: number, vs: number | null = null) =>
      setState((s) => (s.driverIds[0] === id && vs === null ? { ...s, driverIds: [], vsId: null } : { ...s, driverIds: [id], vsId: vs === id ? null : vs })),
    [],
  )
  const setVs = useCallback((vsId: number | null) => setState((s) => ({ ...s, vsId: vsId === s.driverIds[0] ? null : vsId })), [])
  const clearDrivers = useCallback(() => setState((s) => ({ ...s, driverIds: [], vsId: null })), [])
  const value = useMemo(() => ({ ...state, setYear, setEvent, setSession, selectDriver, setVs, clearDrivers }), [state, setYear, setEvent, setSession, selectDriver, setVs, clearDrivers])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useStore(): Store {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore outside StoreProvider')
  return s
}

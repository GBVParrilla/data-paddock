import { lazy, Suspense, useEffect, useId, useMemo, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, eventApi, TURNS_UNRELIABLE, type Driver, type SessionRow, type SessionType } from '../api/client'
import { Boundary, NotFound } from '../components/Boundary'
import { Classification } from '../components/Classification'
import { DeepDive } from '../components/DeepDive'
import { DriverStory } from '../components/DriverStory'
import { WhenVisible } from '../components/WhenVisible'
import { circuitOverlay } from '../lib/circuitOverlay'
import { RaceSheet } from '../components/race/RaceSheet'
import { KeyMoments } from '../components/race/KeyMoments'
import { useFetch } from '../hooks/useFetch'
import { useTitle } from '../hooks/useTitle'
import { isRaceLike, SESSION_ORDER, SESSION_SHORT } from '../lib/f1'
import { planSession } from '../lib/mentions'
import { defaultVs, sessionOrder } from '../lib/compare'
import { useSectorStats } from '../lib/sectors'
import { positionsTitle } from '../lib/takeaways'
import { slotColors } from '../lib/teamColors'
import { useMode } from '../state/mode'
import { useStore } from '../state/store'

// the chart library is loaded only when the position chart scrolls into view
const PositionChart = lazy(() => import('../components/PositionChart').then((m) => ({ default: m.PositionChart })))
const VsStrip = lazy(() => import('../components/CompareView').then((m) => ({ default: m.VsStrip })))

/**
 * A race weekend, story first (decision D2): the 30-second summary, the classification beside the key
 * moments, the positions chart, and everything else behind one "More detail". A tap selects one driver
 * (D8): their circuit map and their panel, with the teammate comparison built in (the vs strip); More
 * detail opens with them. The URL carries `drivers=<id>` and `vs=<id>`; an old `drivers=a,b` link
 * opens a with vs b.
 */
export function RaceWeekend() {
  const params = useParams()
  const eventId = Number(params.eventId)
  const driverRef = params.driverRef
  const [search, setSearch] = useSearchParams()
  const { sessionId, driverIds, vsId, setEvent, setSession, selectDriver, setVs, clearDrivers } = useStore()
  const { expert } = useMode()
  const detailId = useId()
  const hydrated = useRef(false)

  useEffect(() => {
    setEvent(eventId)
  }, [eventId, setEvent])
  useEffect(() => {
    const sid = Number(search.get('session'))
    if (sid) setSession(sid)
    const [a, b] = (search.get('drivers') ?? '').split(',').map(Number).filter(Boolean)
    const vs = Number(search.get('vs')) || b || null  // drivers=a,b (before D8) opens a with vs b
    if (a) selectDriver(a, vs)
    hydrated.current = true
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId])
  // the selection lives in the URL, so a link restores exactly what was on screen
  useEffect(() => {
    if (!hydrated.current) return
    setSearch((p) => {
      const d = driverIds[0]
      if (d) p.set('drivers', String(d)); else p.delete('drivers')
      if (d && vsId) p.set('vs', String(vsId)); else p.delete('vs')
      return p
    }, { replace: true })
  }, [driverIds, vsId, setSearch])

  const event = useFetch((s) => eventApi.get(eventId, s), [eventId], Number.isFinite(eventId))
  const outline = useFetch((s) => api.trackOutline(eventId, s), [eventId])
  const sessionsQ = useFetch((s) => api.sessions(eventId, s), [eventId])
  const sessions: SessionRow[] = useMemo(() => [...(sessionsQ.data ?? [])].sort((a, b) => SESSION_ORDER[a.session_type] - SESSION_ORDER[b.session_type]), [sessionsQ.data])

  useEffect(() => {
    if (!sessions.length || (sessionId !== null && sessions.some((s) => s.id === sessionId))) return
    const done = sessions.filter((s) => s.ingestion.transforms)
    if (done.length) setSession(done[done.length - 1].id)
  }, [sessions, sessionId, setSession])

  const ready = sessionId !== null && sessions.some((s) => s.id === sessionId)
  const session = sessions.find((s) => s.id === sessionId)
  const raceLike = isRaceLike(session?.session_type)
  const headline = useFetch((s) => api.headline(sessionId!, s), [sessionId, ready], ready)
  const detail = useFetch((s) => api.detail(sessionId!, undefined, s), [sessionId, ready], ready)
  const anns = useFetch((s) => api.chartAnnotations(sessionId!, s), [sessionId, ready], ready)
  const spot = useFetch((s) => api.midfieldSpotlight(sessionId!, false, s), [sessionId, ready], ready)
  const moments = useFetch((s) => api.pivotalMoments(sessionId!, s), [sessionId, ready], ready)
  const turnIndex = useFetch((s) => api.turnDeltaIndex(sessionId!, s), [sessionId, ready], ready)

  // /race/:id/driver/:ref (the shareable link for one driver's race): select that driver in the race
  useEffect(() => {
    if (!driverRef || !headline.data) return
    const race = sessions.find((s) => s.session_type === 'R' && s.ingestion.transforms)
    if (race && sessionId !== race.id) { setSession(race.id); return }
    const match = Object.values(headline.data.drivers).find((d) => d.driver_ref === driverRef)
    if (match && !driverIds.includes(match.id)) selectDriver(match.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [driverRef, headline.data, sessions])

  // drop selected drivers who didn't take part in this session
  useEffect(() => {
    if (!headline.data || sessionId === null) return
    const rows = headline.data.practice ?? headline.data.qualifying ?? headline.data.race ?? []
    const present = new Set(rows.map((r) => r.driver_id))
    if (driverIds.some((d) => !present.has(d))) setSession(sessionId, present)
  }, [headline.data, sessionId, driverIds, setSession])

  const drivers = useMemo(() => headline.data?.drivers ?? {}, [headline.data])
  const selected: Driver[] = driverIds.map((id) => drivers[String(id)]).filter(Boolean)
  const mapFor: Driver | undefined = selected[0]
  // the comparison: the one picked, else the teammate that weekend (or the car next to them if the teammate didn't run)
  const vsDriver: Driver | undefined = mapFor && headline.data ? drivers[String(vsId ?? defaultVs(headline.data, mapFor.id))] : undefined
  const started = !!(mapFor && headline.data && sessionOrder(headline.data).find((r) => r.id === mapFor.id)?.ran)
  const colors = slotColors([mapFor?.team, vsDriver?.team])
  const turnDeltas = useFetch((s) => api.turnDeltas(sessionId!, mapFor!.id, s), [sessionId, mapFor?.id, ready], ready && !!mapFor)
  const stats = useSectorStats(detail.data)
  const qualiSession = sessions.find((s) => s.session_type === (session?.session_type === 'S' ? 'SQ' : 'Q') && s.ingestion.transforms)
  const quali = useFetch((s) => api.headline(qualiSession!.id, s), [qualiSession?.id], raceLike && !!qualiSession && !!mapFor)
  const rc = useFetch((s) => api.raceControl(sessionId!, s), [sessionId, ready], ready)
  // a tap shows the story it opens: scroll to it once it renders (a link opens there anyway)
  const storyRef = useRef<HTMLDivElement>(null)
  const reveal = useRef(false)
  const pick = (id: number) => { reveal.current = true; selectDriver(id) }
  useEffect(() => {
    if (!reveal.current || !mapFor) return
    reveal.current = false
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    storyRef.current?.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' })
  }, [mapFor])

  // what the top of the page says, each fact once (lib/mentions)
  const plan = useMemo(
    () => (headline.data && moments.data && session ? planSession(headline.data, moments.data, spot.data, session.session_type, detail.data?.position_by_lap ?? []) : null),
    [headline.data, moments.data, spot.data, session, detail.data],
  )

  // More detail: open once a driver is picked or in Expert mode, unless the reader chose otherwise (?detail=0/1)
  const detailParam = search.get('detail')
  const detailOpen = detailParam === '1' ? true : detailParam === '0' ? false : expert || selected.length > 0
  const toggleDetail = () => setSearch((p) => { p.set('detail', detailOpen ? '0' : '1'); return p }, { replace: true })

  const sessionLabel = session ? SESSION_SHORT[session.session_type as SessionType] : ''
  useTitle(event.data ? `${event.data.name}${sessionLabel ? ` · ${sessionLabel}` : ''}${mapFor ? ` · ${mapFor.code}` : ''}` : null)

  if (!Number.isFinite(eventId) || event.error || (sessionsQ.error && !sessionsQ.loading)) return <NotFound what="race" />

  return (
    <div className="wrap pt-8" data-session={sessionId ?? undefined}>
      <nav className="label mb-3" aria-label="Breadcrumb">
        <Link to="/races" className="hover:text-[var(--text)]">{event.data?.season_year ?? ''} races</Link>
        <span className="mx-2">/</span>
        <span>Round {event.data?.round ?? ''}</span>
      </nav>
      <div className="flex flex-wrap items-start justify-end gap-4 mb-4 min-h-[37px]">
        <div className="seg max-w-full overflow-x-auto" role="tablist" aria-label="Session">
          {sessions.map((s) => (
            <button key={s.id} role="tab" aria-selected={s.id === sessionId} disabled={!s.ingestion.transforms} onClick={() => setSession(s.id)}>
              {SESSION_SHORT[s.session_type as SessionType]}
            </button>
          ))}
        </div>
      </div>

      {sessions.length > 0 && !sessions.some((s) => s.ingestion.transforms) && <div className="panel p-8 text-center t2">No sessions processed for this event yet.</div>}

      {!(sessions.length > 0 && !sessions.some((s) => s.ingestion.transforms)) && (
        <Boundary label="The race sheet">
          <div className="mb-8">
            <RaceSheet event={event.data} outline={outline.data}
              data={ready && session && headline.data && plan ? {
                sessionType: session.session_type, headline: headline.data, sentences: plan.sentences, moments: plan.moments, events: rc.data?.events ?? [],
                overlay: mapFor ? circuitOverlay({ stats, mapFor, turnDeltas: turnDeltas.data, turnsNote: turnDeltas.error?.message === TURNS_UNRELIABLE ? TURNS_UNRELIABLE : undefined }) : undefined,
              } : null} />
          </div>
        </Boundary>
      )}
      {!sessionsQ.loading && sessions.length > 0 && !sessions.some((s) => s.ingestion.transforms) && <h1 className="h-feature mb-6">{event.data?.name}</h1>}

      {/* a picked driver's story comes straight after the sheet, so a driver link opens on it (#62) */}
      {ready && plan && sessionId !== null && mapFor && (
        <div className="mb-4 scroll-mt-20" ref={storyRef} data-story-slot>
        <Boundary key={mapFor.id} label={`${mapFor.name}'s story`}>
          <DriverStory eventId={eventId} sessionId={sessionId} sessions={sessions} driver={mapFor} color={colors[0]} onSession={setSession}>
            {started && vsDriver && headline.data && (
              <Boundary label="The comparison">
                <Suspense fallback={<div className="skeleton h-40 mx-5 mb-5" />}>
                  <VsStrip eventId={eventId} sessionId={sessionId} headline={headline.data} quali={quali.data?.qualifying ?? null} a={mapFor} b={vsDriver}
                    colors={[colors[0], colors[1]]} cases={rc.data?.cases ?? []} onVs={setVs} onRead={pick} />
                </Suspense>
              </Boundary>
            )}
          </DriverStory>
        </Boundary>
        </div>
      )}

      {ready && plan && (
        <div className="grid lg:grid-cols-12 gap-4 items-start">
          <section className="panel lg:col-span-6 xl:col-span-5 flex flex-col min-w-0" aria-label="Classification">
            <div className="panel-head pb-2">
              <h2 className="h2">Classification</h2>
              {selected.length > 0 ? <button className="btn-ghost text-[12px]" onClick={clearDrivers}>Clear selection</button> : <span className="label" data-hint>Pick a driver</span>}
            </div>
            <div className="px-1.5 pb-1.5 overflow-x-auto">
              <Boundary label="The classification">
                {headline.data ? <Classification headline={headline.data} selected={driverIds} colors={colors} onSelect={pick} /> : <div className="skeleton h-[600px] m-2" />}
              </Boundary>
            </div>
          </section>

          <div className="lg:col-span-6 xl:col-span-7 flex flex-col gap-4 min-w-0">
            <Boundary label="Key moments">
              {plan && headline.data
                ? <KeyMoments moments={plan.moments} midfield={plan.midfield} drivers={drivers} onPick={pick} />
                : moments.loading && <div className="panel skeleton h-64" />}
            </Boundary>
          </div>
        </div>
      )}

      {ready && plan && raceLike && (
        <section className="panel mt-4" aria-label="Race positions">
          <div className="panel-head">
            <h2 className="h2">{detail.data && headline.data ? positionsTitle(detail.data.position_by_lap, headline.data.race ?? [], drivers) : 'Positions by lap'}</h2>
          </div>
          <div className="panel-body pt-2">
            <Boundary label="The position chart">
              {detail.data && headline.data
                ? <WhenVisible minHeight={360}><Suspense fallback={<div className="skeleton h-[360px]" />}>
                    <PositionChart rows={detail.data.position_by_lap} drivers={drivers} race={headline.data.race ?? []} selected={mapFor ? [mapFor.id, ...(vsDriver && started ? [vsDriver.id] : [])] : []} annotations={anns.data ?? []} pitStops={detail.data.pit_stops} stints={detail.data.stint_timeline} onSelect={pick} />
                  </Suspense></WhenVisible>
                : <div className="skeleton h-[420px]" />}
            </Boundary>
          </div>
        </section>
      )}

      {ready && plan && sessionId !== null && (
        <div className="mt-4 space-y-4">
          {detail.data && headline.data && session && (
            <section className="panel" aria-label="More detail">
              <button type="button" className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-[var(--hover)]"
                aria-expanded={detailOpen} aria-controls={detailId} onClick={toggleDetail}>
                <span className="h2">More detail</span>
                <span className="label flex items-center gap-2">
                  <span className="hidden sm:inline">{raceLike ? 'Tyres, sectors and race control' : 'Tyres, long runs, sectors and race control'}</span>
                  <span aria-hidden="true" className={`transition-transform ${detailOpen ? 'rotate-90' : ''}`}>›</span>
                </span>
              </button>
              {detailOpen && (
                <div id={detailId} className="border-t" style={{ borderColor: 'var(--line)' }}>
                  <Boundary label="The deep dive"><WhenVisible minHeight={420}><DeepDive sessionType={session.session_type} sessionId={sessionId} detail={detail.data} headline={headline.data} selected={selected} turnsFor={turnIndex.data?.drivers ?? null} /></WhenVisible></Boundary>
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  )
}


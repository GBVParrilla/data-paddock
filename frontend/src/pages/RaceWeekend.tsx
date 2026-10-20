import { lazy, Suspense, useEffect, useId, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, eventApi, TURNS_UNRELIABLE, type Driver, type SessionRow, type SessionType } from '../api/client'
import { Boundary, NotFound } from '../components/Boundary'
import { Classification } from '../components/Classification'
import { DeepDive } from '../components/DeepDive'
import { DriverStory } from '../components/DriverStory'
import { Freshness } from '../components/Freshness'
import { WhenVisible } from '../components/WhenVisible'
import { CircuitPanel, SectorStrip } from '../components/race/CircuitPanel'
import { KeyMoments } from '../components/race/KeyMoments'
import { SessionSummary } from '../components/race/SessionSummary'
import { useFetch } from '../hooks/useFetch'
import { useTitle } from '../hooks/useTitle'
import { isRaceLike, SESSION_ORDER, SESSION_SHORT, shortDate } from '../lib/f1'
import { planSession } from '../lib/mentions'
import { sectorRanks, useSectorStats } from '../lib/sectors'
import { positionsTitle } from '../lib/takeaways'
import { slotColors } from '../lib/teamColors'
import { useMode } from '../state/mode'
import { useStore } from '../state/store'

// the chart library is loaded only when the position chart scrolls into view
const PositionChart = lazy(() => import('../components/PositionChart').then((m) => ({ default: m.PositionChart })))
const CompareView = lazy(() => import('../components/CompareView').then((m) => ({ default: m.CompareView })))

/**
 * A race weekend, story first (decision D2): the 30-second summary, the classification beside the key
 * moments, the positions chart, and everything else behind one "More detail". Picking a driver adds
 * their circuit map and story, and opens More detail; Expert mode keeps it open.
 */
export function RaceWeekend() {
  const params = useParams()
  const eventId = Number(params.eventId)
  const driverRef = params.driverRef
  const [search, setSearch] = useSearchParams()
  const { sessionId, driverIds, setEvent, setSession, toggleDriver, clearDrivers } = useStore()
  const { expert } = useMode()
  const [mapDriver, setMapDriver] = useState(0)
  const detailId = useId()

  useEffect(() => {
    setEvent(eventId)
  }, [eventId, setEvent])
  useEffect(() => {
    const sid = Number(search.get('session'))
    if (sid) setSession(sid)
    for (const d of (search.get('drivers') ?? '').split(',').map(Number).filter(Boolean).slice(0, 2)) toggleDriver(d)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId])

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
    if (match && !driverIds.includes(match.id)) { clearDrivers(); toggleDriver(match.id) }
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
  const colors = slotColors(selected.map((d) => d.team))
  const mapIdx = Math.min(mapDriver, Math.max(0, selected.length - 1))
  const mapFor = selected[mapIdx]
  const turnDeltas = useFetch((s) => api.turnDeltas(sessionId!, mapFor!.id, s), [sessionId, mapFor?.id, ready], ready && !!mapFor)
  const stats = useSectorStats(detail.data)
  const pick = (id: number) => { clearDrivers(); toggleDriver(id) }

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
  useTitle(event.data ? `${event.data.name}${sessionLabel ? ` · ${sessionLabel}` : ''}${selected[0] ? ` · ${selected.map((d) => d.code).join(' vs ')}` : ''}` : null)

  if (!Number.isFinite(eventId) || event.error || (sessionsQ.error && !sessionsQ.loading)) return <NotFound what="race" />

  return (
    <div className="wrap pt-8" data-session={sessionId ?? undefined}>
      <nav className="label mb-3" aria-label="Breadcrumb">
        <Link to="/races" className="hover:text-[var(--text)]">{event.data?.season_year ?? ''} races</Link>
        <span className="mx-2">/</span>
        <span>Round {event.data?.round ?? ''}</span>
      </nav>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h1 className="h-feature">{event.data?.name ?? <span className="skeleton inline-block h-10 w-72 align-middle" />}</h1>
          <p className="t2 mt-2 text-[13px]">{event.data && [event.data.circuit_name, event.data.country, shortDate(event.data.event_date)].filter(Boolean).join(' · ')}</p>
          <Freshness className="mt-1" />
        </div>
        <div className="seg max-w-full overflow-x-auto" role="tablist" aria-label="Session">
          {sessions.map((s) => (
            <button key={s.id} role="tab" aria-selected={s.id === sessionId} disabled={!s.ingestion.transforms} onClick={() => setSession(s.id)}>
              {SESSION_SHORT[s.session_type as SessionType]}
            </button>
          ))}
        </div>
      </div>

      {sessions.length > 0 && !sessions.some((s) => s.ingestion.transforms) && <div className="panel p-8 text-center t2">No sessions processed for this event yet.</div>}
      {sessionsQ.loading && <div className="skeleton h-40 mb-4" />}

      {ready && session && (
        <Boundary label="The session summary">
          {headline.data && moments.data && plan
            ? <div className="mb-4"><SessionSummary headline={headline.data} moments={moments.data} sentences={plan.sentences} sessionType={session.session_type} /></div>
            : <div className="skeleton h-[172px] mb-4" />}
        </Boundary>
      )}

      {ready && (
        <div className="grid lg:grid-cols-12 gap-4 items-start">
          <section className="panel lg:col-span-6 xl:col-span-5 flex flex-col min-w-0" aria-label="Classification">
            <div className="panel-head pb-2">
              <h2 className="h2">Classification</h2>
              {selected.length > 0 ? <button className="btn-ghost text-[12px]" onClick={clearDrivers}>Clear selection</button> : <span className="label" data-hint>Pick up to two drivers</span>}
            </div>
            <div className="px-1.5 pb-1.5 overflow-x-auto">
              <Boundary label="The classification">
                {headline.data ? <Classification headline={headline.data} selected={driverIds} colors={colors} onSelect={toggleDriver} /> : <div className="skeleton h-[600px] m-2" />}
              </Boundary>
            </div>
          </section>

          <div className="lg:col-span-6 xl:col-span-7 flex flex-col gap-4 min-w-0">
            {mapFor && headline.data && (
              <Boundary label="The circuit map">
                <CircuitPanel outline={outline.data} outlineLoading={outline.loading} stats={stats} headline={headline.data} mapFor={mapFor} selected={selected} mapIdx={mapIdx} onMapIdx={setMapDriver} turnDeltas={turnDeltas.data} turnsNote={turnDeltas.error?.message === TURNS_UNRELIABLE ? TURNS_UNRELIABLE : undefined} />
              </Boundary>
            )}
            <Boundary label="Key moments">
              {plan && headline.data
                ? <KeyMoments moments={plan.moments} midfield={plan.midfield} drivers={drivers} onPick={pick}
                    top={!mapFor ? <SectorStrip outline={outline.data} stats={stats} headline={headline.data} /> : undefined} />
                : moments.loading && <div className="panel skeleton h-64" />}
            </Boundary>
          </div>
        </div>
      )}

      {ready && raceLike && (
        <section className="panel mt-4" aria-label="Race positions">
          <div className="panel-head">
            <h2 className="h2">{detail.data && headline.data ? positionsTitle(detail.data.position_by_lap, headline.data.race ?? [], drivers) : 'Positions by lap'}</h2>
          </div>
          <div className="panel-body pt-2">
            <Boundary label="The position chart">
              {detail.data && headline.data
                ? <WhenVisible minHeight={360}><Suspense fallback={<div className="skeleton h-[360px]" />}>
                    <PositionChart rows={detail.data.position_by_lap} drivers={drivers} race={headline.data.race ?? []} selected={driverIds} annotations={anns.data ?? []} pitStops={detail.data.pit_stops} stints={detail.data.stint_timeline} onSelect={toggleDriver} />
                  </Suspense></WhenVisible>
                : <div className="skeleton h-[420px]" />}
            </Boundary>
          </div>
        </section>
      )}

      {ready && sessionId !== null && (
        <div className="mt-4 space-y-4">
          {selected.length === 2 && headline.data && <Boundary label="The comparison"><Suspense fallback={<div className="panel skeleton h-64" />}><CompareView eventId={eventId} sessionId={sessionId} headline={headline.data} a={selected[0]} b={selected[1]} colors={colors} /></Suspense></Boundary>}
          {selected.map((d, i) => (
            <Boundary key={d.id} label={`${d.name}'s story`}>
              <DriverStory eventId={eventId} sessionId={sessionId} sessions={sessions} driver={d} color={colors[i]} onSession={setSession} sectorRanks={sectorRanks(stats, d.id)} />
            </Boundary>
          ))}
          {detail.data && headline.data && session && (
            <section className="panel" aria-label="More detail">
              <button type="button" className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-[var(--hover)] rounded-[inherit]"
                aria-expanded={detailOpen} aria-controls={detailId} onClick={toggleDetail}>
                <span className="h2">More detail</span>
                <span className="label flex items-center gap-2">
                  <span className="hidden sm:inline">{raceLike ? 'Tyres, sectors and race control' : 'Tyres, long runs, sectors and race control'}</span>
                  <span aria-hidden="true" className={`transition-transform ${detailOpen ? 'rotate-90' : ''}`}>›</span>
                </span>
              </button>
              {detailOpen && (
                <div id={detailId} className="border-t" style={{ borderColor: 'var(--line)' }}>
                  <Boundary label="The deep dive"><DeepDive sessionType={session.session_type} sessionId={sessionId} detail={detail.data} headline={headline.data} selected={selected} turnsFor={turnIndex.data?.drivers ?? null} /></Boundary>
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  )
}

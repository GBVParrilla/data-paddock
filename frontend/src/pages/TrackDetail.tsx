import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, eventApi, SESSION_LABEL, type Driver, type SessionRow } from '../api/client'
import { ComparePanel } from '../components/ComparePanel'
import { Leaderboard } from '../components/Leaderboard'
import { MidfieldCard } from '../components/MidfieldCard'
import { NarrativePanel } from '../components/NarrativePanel'
import { PositionChart } from '../components/PositionChart'
import { TrackOutline, type SectorMode } from '../components/TrackOutline'
import { TurnTimesPanel } from '../components/TurnTimesPanel'
import { useFetch } from '../hooks/useFetch'
import { slotColors } from '../lib/teamColors'
import { useStore } from '../state/store'

const ORDER: Record<string, number> = { FP1: 0, FP2: 1, FP3: 2, SQ: 3, S: 4, Q: 5, R: 6 }

interface SatAdjust { rotationDeg: number; mirrored: boolean }
const DEFAULT_SAT_ADJUST: SatAdjust = { rotationDeg: 0, mirrored: false }

function loadSatAdjust(eventId: number): SatAdjust {
  try {
    const raw = localStorage.getItem(`f1tracker:sat-adjust:${eventId}`)
    if (raw) return { ...DEFAULT_SAT_ADJUST, ...JSON.parse(raw) }
  } catch {
    /* ignore - private browsing, etc. */
  }
  return DEFAULT_SAT_ADJUST
}

export function TrackDetail() {
  const eventId = Number(useParams().eventId)
  const { sessionId, driverIds, setEvent, setSession, toggleDriver, clearDrivers } = useStore()
  const [colorDriver, setColorDriver] = useState<0 | 1>(0)
  const [spotlightId, setSpotlightId] = useState<number | null>(null)
  const [mapTheme, setMapTheme] = useState<'track' | 'satellite'>('track')
  const [satAdjust, setSatAdjust] = useState<SatAdjust>(() => loadSatAdjust(eventId))

  useEffect(() => setEvent(eventId), [eventId, setEvent])
  // deep links (used by "Flag a problem"): ?session=<id>&drivers=<id>,<id>
  const [search] = useSearchParams()
  useEffect(() => {
    const sid = Number(search.get('session'))
    if (sid) setSession(sid)
    for (const d of (search.get('drivers') ?? '').split(',').map(Number).filter(Boolean).slice(0, 2)) toggleDriver(d)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId])
  useEffect(() => setSatAdjust(loadSatAdjust(eventId)), [eventId])
  const updateSatAdjust = (patch: Partial<SatAdjust>) => {
    setSatAdjust((prev) => {
      const next = { ...prev, ...patch }
      try {
        localStorage.setItem(`f1tracker:sat-adjust:${eventId}`, JSON.stringify(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }
  const event = useFetch((s) => eventApi.get(eventId, s), [eventId])
  const outline = useFetch((s) => api.trackOutline(eventId, s), [eventId])
  const sessions = useFetch((s) => api.sessions(eventId, s), [eventId])

  // default session: the race if ingested, else the last ingested session
  useEffect(() => {
    if (!sessions.data || sessionId !== null) return
    const ready = sessions.data.filter((s) => s.ingestion.transforms).sort((a, b) => ORDER[a.session_type] - ORDER[b.session_type])
    if (ready.length) setSession(ready[ready.length - 1].id)
  }, [sessions.data, sessionId, setSession])

  const headline = useFetch((s) => api.headline(sessionId!, s), [sessionId], sessionId !== null)
  const detail = useFetch((s) => api.detail(sessionId!, undefined, s), [sessionId], sessionId !== null)
  const annotations = useFetch((s) => api.chartAnnotations(sessionId!, s), [sessionId], sessionId !== null)

  // keep selected drivers only if they took part in the newly selected session
  useEffect(() => {
    if (!headline.data || sessionId === null) return
    const rows = headline.data.practice ?? headline.data.qualifying ?? headline.data.race ?? []
    const present = new Set(rows.map((r) => r.driver_id))
    if (driverIds.some((d) => !present.has(d))) setSession(sessionId, present)
  }, [headline.data, sessionId, driverIds, setSession])

  const drivers = headline.data?.drivers ?? {}
  const selected: Driver[] = driverIds.map((id) => drivers[String(id)]).filter(Boolean)
  const highlightColors = useMemo(() => slotColors(selected.map((d) => d.team)), [selected])
  const session: SessionRow | undefined = sessions.data?.find((s) => s.id === sessionId)
  const isRace = session?.session_type === 'R' || session?.session_type === 'S'

  const colorDriverId: number | undefined = driverIds[Math.min(colorDriver, driverIds.length - 1)]
  const turnDeltas = useFetch((s) => api.turnDeltas(sessionId!, colorDriverId!, s), [sessionId, colorDriverId], sessionId !== null && colorDriverId !== undefined)
  const turnDeltasMs = useMemo(() => {
    if (!turnDeltas.data) return undefined
    return Object.fromEntries(turnDeltas.data.turns.map((t) => [t.number, t.delta_ms]))
  }, [turnDeltas.data])

  // sector colouring: purple/green/yellow/red vs the field average, or plain purple for the session-best view
  const sectorMode: SectorMode = useMemo(() => {
    const deltas = detail.data?.sector_deltas ?? []
    if (!deltas.length) return { kind: 'plain' }
    const colorId = colorDriverId
    const perDriverBest: Record<1 | 2 | 3, Map<number, number>> = { 1: new Map(), 2: new Map(), 3: new Map() }
    for (const d of deltas) {
      if (d.delta_ms === null) continue
      const m = perDriverBest[d.sector]
      const cur = m.get(d.driver_id)
      if (cur === undefined || d.delta_ms < cur) m.set(d.driver_id, d.delta_ms)
    }
    const avg: Record<1 | 2 | 3, number | null> = { 1: null, 2: null, 3: null }
    for (const s of [1, 2, 3] as const) {
      const vals = [...perDriverBest[s].values()]
      avg[s] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
    }
    if (colorId !== undefined) {
      const best: Record<1 | 2 | 3, number | null> = { 1: null, 2: null, 3: null }
      for (const s of [1, 2, 3] as const) best[s] = perDriverBest[s].get(colorId) ?? null
      return { kind: 'driver', label: drivers[String(colorId)]?.name ?? `Driver ${colorId}`, deltas: best, avg }
    }
    const best: Record<1 | 2 | 3, { ms: number | null; holder: string | null }> = { 1: { ms: null, holder: null }, 2: { ms: null, holder: null }, 3: { ms: null, holder: null } }
    for (const d of deltas) if (d.delta_ms === 0) best[d.sector] = { ms: d.session_best_sector_ms, holder: drivers[String(d.driver_id)]?.name ?? null }
    return { kind: 'session-best', best }
  }, [detail.data, colorDriverId, drivers])

  const selectOnly = (id: number) => { clearDrivers(); toggleDriver(id) }
  const hasGeo = !!outline.data?.geo_bbox

  return (
    <div>
      <div className="f1-header">
        <div className="max-w-7xl mx-auto px-4 py-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link to="/" className="text-sm muted hover:underline">← All races</Link>
            <h1 className="display text-2xl sm:text-3xl mt-0.5">{event.data?.name ?? '…'}</h1>
            <p className="muted text-sm">{event.data && `Round ${event.data.round} · ${event.data.circuit_name} · ${event.data.country}${event.data.has_sprint ? ' · Sprint weekend' : ''}`}</p>
          </div>
          <nav className="flex gap-1 flex-wrap" aria-label="Session">
            {sessions.data?.slice().sort((a, b) => ORDER[a.session_type] - ORDER[b.session_type]).map((s) => (
              <button key={s.id} className="btn" aria-pressed={s.id === sessionId} disabled={!s.ingestion.transforms} title={s.ingestion.transforms ? '' : 'Not ingested yet'} onClick={() => setSession(s.id)}>
                {SESSION_LABEL[s.session_type]}
              </button>
            ))}
          </nav>
        </div>
        <div className="checker-strip" />
      </div>

    <div className="max-w-7xl mx-auto px-4 py-5 space-y-5">
      {headline.data?.summary && <p className="text-sm card px-4 py-2 border-l-4" style={{ borderColor: 'var(--accent)' }}>{headline.data.summary}</p>}

      <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-5 items-start">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] uppercase tracking-wide faint">Circuit</span>
            <div className="flex gap-1">
              <button className="btn" aria-pressed={mapTheme === 'track'} onClick={() => setMapTheme('track')}>Track</button>
              <button className="btn" aria-pressed={mapTheme === 'satellite'} disabled={!hasGeo} title={hasGeo ? '' : 'No circuit location data for this event'} onClick={() => setMapTheme('satellite')}>Satellite</button>
            </div>
          </div>
          {outline.data ? (
            <TrackOutline outline={outline.data} mode={sectorMode} size="100%" theme={mapTheme} satelliteRotationDeg={satAdjust.rotationDeg} satelliteMirror={satAdjust.mirrored} turnDeltasMs={turnDeltasMs} />
          ) : (
            <div className="faint text-sm">{outline.loading ? 'Loading track…' : outline.error?.message}</div>
          )}
          {mapTheme === 'satellite' && hasGeo && (
            <div className="mt-3 pt-3 border-t text-xs space-y-2" style={{ borderColor: 'var(--line)' }}>
              <div className="flex items-center gap-2">
                <span className="muted w-14">Rotate</span>
                <input type="range" min={-180} max={180} step={1} value={satAdjust.rotationDeg} onChange={(e) => updateSatAdjust({ rotationDeg: Number(e.target.value) })} className="flex-1" />
                <span className="font-mono w-10 text-right">{satAdjust.rotationDeg}°</span>
              </div>
              <div className="flex items-center gap-2">
                <button className="btn" aria-pressed={satAdjust.mirrored} onClick={() => updateSatAdjust({ mirrored: !satAdjust.mirrored })}>Flip</button>
                <button className="btn" onClick={() => updateSatAdjust(DEFAULT_SAT_ADJUST)}>Reset</button>
                <span className="faint">Drag to line the outline up with the road - saved for this track.</span>
              </div>
            </div>
          )}
          {driverIds.length === 2 && (
            <div className="flex items-center gap-2 mt-3 text-xs">
              <span className="muted">Sector colouring:</span>
              {[0, 1].map((i) => (
                <button key={i} className="btn" aria-pressed={colorDriver === i} onClick={() => setColorDriver(i as 0 | 1)} style={colorDriver === i ? { background: highlightColors[i], borderColor: highlightColors[i] } : undefined}>{selected[i]?.code ?? selected[i]?.name ?? `Driver ${i + 1}`}</button>
              ))}
            </div>
          )}
          {driverIds.length > 0 && (
            <div className="mt-2 text-xs muted flex items-center gap-2 flex-wrap">
              Selected: {selected.map((d, i) => <span key={d.id} className="px-2 py-0.5 rounded text-white font-semibold" style={{ background: highlightColors[i] }}>{d.name}</span>)}
              <button className="btn" onClick={clearDrivers}>Clear</button>
              {driverIds.length === 1 && <span className="faint">Click another driver to compare.</span>}
            </div>
          )}
        </div>
        <div className="space-y-4">
          {sessionId !== null && <MidfieldCard sessionId={sessionId} onSelect={selectOnly} onStory={setSpotlightId} />}
          {headline.data && <Leaderboard headline={headline.data} selected={driverIds} highlightColors={highlightColors} spotlightId={spotlightId} onSelect={toggleDriver} />}
          {headline.loading && <div className="muted text-sm">Loading results…</div>}
          {headline.error && <div className="text-sm" style={{ color: 'var(--status-critical)' }}>{headline.error.message}</div>}
        </div>
      </div>

      {isRace && detail.data && (
        <section className="card p-4">
          <h2 className="font-semibold mb-2 not-italic normal-case text-base">Position by lap {driverIds.length === 0 && <span className="muted font-normal text-sm">· select a driver to highlight</span>}</h2>
          <PositionChart rows={detail.data.position_by_lap} drivers={drivers} highlighted={driverIds} highlightColors={highlightColors} annotations={annotations.data ?? []} pitStops={detail.data.pit_stops} stints={detail.data.stint_timeline} />
        </section>
      )}
      {!isRace && annotations.data && annotations.data.length > 0 && (
        <section className="card p-4">
          <h2 className="font-semibold mb-1 not-italic normal-case text-base">Pivotal moments</h2>
          <ul className="text-sm list-disc pl-5 space-y-1">{annotations.data.map((a, i) => <li key={i}><span className="font-semibold">{a.label}</span> <span className="muted">{a.description}</span></li>)}</ul>
        </section>
      )}

      {sessionId !== null && selected.length > 0 && (
        <section className={`grid gap-4 ${selected.length === 2 ? 'md:grid-cols-2' : ''}`}>
          {selected.map((d, i) => <NarrativePanel key={d.id} sessionId={sessionId} eventId={eventId} driver={d} accent={highlightColors[i]} />)}
        </section>
      )}
      {sessionId !== null && selected.length > 0 && (
        <section className={`grid gap-4 ${selected.length === 2 ? 'md:grid-cols-2' : ''}`}>
          {selected.map((d, i) => <TurnTimesPanel key={d.id} sessionId={sessionId} driver={d} accent={highlightColors[i]} />)}
        </section>
      )}
      {sessionId !== null && selected.length === 2 && <ComparePanel sessionId={sessionId} eventId={eventId} a={selected[0]} b={selected[1]} colors={highlightColors} />}
    </div>
    </div>
  )
}

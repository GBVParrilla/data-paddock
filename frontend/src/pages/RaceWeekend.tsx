import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, eventApi, fmtMs, type Driver, type Headline, type MidfieldStory, type PivotalMoment, type SessionRow, type SessionType } from '../api/client'
import { Classification } from '../components/Classification'
import { CompareView } from '../components/CompareView'
import { DeepDive } from '../components/DeepDive'
import { DriverStory } from '../components/DriverStory'
import { PositionChart } from '../components/PositionChart'
import { TrackMap } from '../components/TrackMap'
import { useFetch } from '../hooks/useFetch'
import { isRaceLike, SESSION_ORDER, SESSION_SHORT, sectorTier, shortDate, TIER_COLOR, TIER_LABEL, turnTier, type Tier } from '../lib/f1'
import { slotColors, teamColor } from '../lib/teamColors'
import { useStore } from '../state/store'

type TileData = { label: string; value: string; sub?: string; color?: string; onClick?: () => void }

function Tile({ t }: { t: TileData }) {
  const body = (
    <>
      <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: t.color ?? 'var(--line-2)' }} />
      <div className="kicker">{t.label}</div>
      <div className="stat mt-2.5 truncate">{t.value}</div>
      {t.sub && <div className="text-[12.5px] t2 mt-1 line-clamp-2">{t.sub}</div>}
    </>
  )
  const cls = 'panel relative overflow-hidden px-4 pt-5 pb-4 text-left flex flex-col items-stretch justify-start min-w-0'
  return t.onClick
    ? <button onClick={t.onClick} className={`${cls} lift`}>{body}</button>
    : <div className={cls}>{body}</div>
}

const MOMENT_LABEL: Record<string, string> = { safety_car: 'Neutralised', pit_stop: 'Pit stop', penalty: 'Penalty', position_swing: 'Move', retirement: 'Retirement', overtake: 'Overtake', fastest_lap: 'Fastest lap' }

// race-control messages arrive in capitals ("STOP-AND-GO PENALTY FOR CAR 43 (COL) - ...")
const tidy = (text: string) => {
  const t = text.replace(/^[^-]+ - Lap \d+: /, '').replace(/ \d+ pit stop\(s\) were made under it\./, '')
  if (t !== t.toUpperCase()) return t
  const lower = t.toLowerCase().replace(/\(([a-z]{3})\)/g, (_, c: string) => `(${c.toUpperCase()})`).replace(/ - /g, ': ')
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}

/** The session's biggest moments in lap order: the race at a glance, and a way into a driver's story. */
function KeyMoments({ moments, drivers, onPick }: { moments: PivotalMoment[]; drivers: Headline['drivers']; onPick: (id: number) => void }) {
  const top = [...moments].sort((a, b) => b.magnitude_score - a.magnitude_score).slice(0, 6).sort((a, b) => (a.lap_number ?? 0) - (b.lap_number ?? 0))
  if (!top.length) return null
  return (
    <section className="panel" aria-label="Key moments">
      <div className="panel-head"><h2 className="h2">Key moments</h2><span className="label">Largest swings, in lap order</span></div>
      <ol className="px-4 pb-3 pt-2">
        {top.map((m) => {
          const d = m.driver_id !== null ? drivers[String(m.driver_id)] : undefined
          const row = (
            <>
              <span className="num t3 text-[12px] w-9 shrink-0 pt-px">{m.lap_number ? `L${m.lap_number}` : '–'}</span>
              <span className="swatch h-4 mt-px shrink-0" style={{ background: d ? teamColor(d.team) : 'var(--yellow)' }} />
              <span className="min-w-0">
                <span className="label mr-2">{/red flag/i.test(m.description) ? 'Red flag' : MOMENT_LABEL[m.moment_type] ?? m.moment_type.replace('_', ' ')}</span>
                <span className="text-[13px] t2">{tidy(m.description)}</span>
              </span>
            </>
          )
          return (
            <li key={m.id} className="border-t first:border-t-0" style={{ borderColor: 'var(--line)' }}>
              {d
                ? <button onClick={() => onPick(d.id)} className="w-full flex items-start gap-3 py-2.5 text-left hover:bg-[var(--hover)] rounded-md px-1">{row}</button>
                : <div className="flex items-start gap-3 py-2.5 px-1">{row}</div>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

function tilesFor(h: Headline, spot: MidfieldStory | null | undefined, onPick: (id: number) => void, fastest?: { id: number; ms: number }): TileData[] {
  const d = (id?: number) => (id !== undefined ? h.drivers[String(id)] : undefined)
  const tiles: TileData[] = []
  if (h.race) {
    const fin = [...h.race].sort((a, b) => (a.finish_position ?? 99) - (b.finish_position ?? 99))
    const win = d(fin[0]?.driver_id)
    tiles.push({ label: 'Winner', value: win?.name ?? '–', sub: win?.team ?? '', color: teamColor(win?.team) })
    const climb = [...h.race].filter((r) => r.finish_position).sort((a, b) => (b.positions_gained ?? 0) - (a.positions_gained ?? 0))[0]
    const cd = d(climb?.driver_id)
    tiles.push({ label: 'Biggest climb', value: climb?.positions_gained ? `${cd?.name} +${climb.positions_gained}` : '–', sub: climb ? `P${climb.grid_position} to P${climb.finish_position}` : '', color: teamColor(cd?.team), onClick: cd ? () => onPick(cd.id) : undefined })
    const out = h.race.filter((r) => !r.finish_position || (r.status && /retired|dnf|accident|collision|disqualified/i.test(r.status))).length
    const fd = d(fastest?.id)
    tiles.push({ label: 'Fastest lap', value: fd ? `${fd.name}` : '–', sub: `${fastest ? fmtMs(fastest.ms) : ''}${out ? ` · ${out} did not finish` : ''}`, color: fd ? teamColor(fd.team) : undefined, onClick: fd ? () => onPick(fd.id) : undefined })
  } else if (h.qualifying) {
    const q = [...h.qualifying].sort((a, b) => (a.position ?? 99) - (b.position ?? 99))
    const pole = d(q[0]?.driver_id)
    tiles.push({ label: 'Pole position', value: pole?.name ?? '–', sub: pole?.team ?? '', color: teamColor(pole?.team) })
    tiles.push({ label: 'Margin to P2', value: q[1]?.gap_to_pole_ms ? `${fmtMs(q[1].gap_to_pole_ms)}s` : '–', sub: d(q[1]?.driver_id)?.name })
    tiles.push({ label: 'Gap pole to P10', value: q[9]?.gap_to_pole_ms ? `${fmtMs(q[9].gap_to_pole_ms)}s` : '–', sub: 'How tight the top ten was' })
  } else if (h.practice) {
    const p = [...h.practice].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
    const top = d(p[0]?.driver_id)
    tiles.push({ label: 'Fastest', value: top?.name ?? '–', sub: p[0] ? fmtMs(p[0].fastest_lap_ms) : '', color: teamColor(top?.team) })
    tiles.push({ label: 'Gap P1 to P10', value: p[9]?.gap_to_fastest_ms ? `${fmtMs(p[9].gap_to_fastest_ms)}s` : '–', sub: 'Spread of the top ten' })
    tiles.push({ label: 'Drivers set a time', value: String(p.filter((r) => r.fastest_lap_ms).length), sub: `of ${p.length} entered` })
  }
  if (spot) tiles.push({ label: 'Midfield story', value: spot.driver, sub: spot.reason.split('. ')[0], color: teamColor(spot.team), onClick: () => onPick(spot.driver_id) })
  else tiles.push({ label: 'Midfield story', value: '–', sub: 'Nothing stood out this session' })
  return tiles
}

const STORY_TYPE: Record<string, string> = {
  big_mover: 'Big climb', close_battle: 'Close battle', points_from_deep: 'Points from deep', quali_overperformer: 'Qualifying surprise', long_run_pace: 'Long-run pace',
}

// runners-up only carry their reason text, so name the storyline from it
const tagFor = (reason: string) =>
  /climbed|gained/.test(reason) ? 'Big climb' : /scored from/.test(reason) ? 'Points from deep' : /qualified/.test(reason) ? 'Qualifying'
    : /long run|long-run/i.test(reason) ? 'Long-run pace' : /behind|ahead of/.test(reason) ? 'Close battle' : 'Midfield story'

/** Midfield and underdog storylines, given the same billing as the podium: the way into a driver's weekend. */
function BeyondPodium({ spot, drivers, onPick }: { spot: MidfieldStory; drivers: Headline['drivers']; onPick: (id: number) => void }) {
  const cards = [
    { id: spot.driver_id, name: spot.driver, reason: spot.reason, tag: STORY_TYPE[spot.story_types[0]] ?? 'Midfield story' },
    ...spot.runners_up.slice(0, 3).map((r) => ({ id: r.driver_id, name: r.driver, reason: r.reason, tag: tagFor(r.reason) })),
  ]
  // the detector writes "Pierre Gasly climbed ... Pierre Gasly finished ..."; drop the repeated name
  const trim = (name: string, text: string) => text.split(/(?<=\.)\s+/).slice(0, 2).map((t) => t.replace(new RegExp(`^${name} `), '')).map((t) => t.charAt(0).toUpperCase() + t.slice(1)).join(' ')
  return (
    <section className="panel" aria-label="Beyond the podium">
      <div className="panel-head"><h2 className="h2">Beyond the podium</h2><span className="label">Pick a driver to follow their weekend</span></div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4">
        {cards.map((c, i) => {
          const d = drivers[String(c.id)]
          return (
            <button key={c.id} onClick={() => onPick(c.id)} className="lift relative overflow-hidden rounded-lg border text-left p-4 pt-5 flex flex-col" style={{ borderColor: 'var(--line)', background: i === 0 ? 'var(--panel-2)' : 'transparent' }}>
              <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: teamColor(d?.team) }} />
              <div className="kicker">{c.tag}</div>
              <div className="display font-bold text-[19px] mt-2 leading-tight">{c.name}</div>
              <div className="label mt-0.5">{d?.team}</div>
              <p className="text-[13px] t2 mt-3 flex-1">{trim(c.name, c.reason)}</p>
              <div className="text-[12.5px] font-medium mt-4">Read their weekend <span aria-hidden="true">→</span></div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

export function RaceWeekend() {
  const eventId = Number(useParams().eventId)
  const [search] = useSearchParams()
  const { sessionId, driverIds, setEvent, setSession, toggleDriver, clearDrivers } = useStore()
  const [mapDriver, setMapDriver] = useState(0)

  useEffect(() => {
    setEvent(eventId)
  }, [eventId, setEvent])
  useEffect(() => {
    const sid = Number(search.get('session'))
    if (sid) setSession(sid)
    for (const d of (search.get('drivers') ?? '').split(',').map(Number).filter(Boolean).slice(0, 2)) toggleDriver(d)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId])

  const event = useFetch((s) => eventApi.get(eventId, s), [eventId])
  const outline = useFetch((s) => api.trackOutline(eventId, s), [eventId])
  const sessionsQ = useFetch((s) => api.sessions(eventId, s), [eventId])
  const sessions: SessionRow[] = useMemo(() => [...(sessionsQ.data ?? [])].sort((a, b) => SESSION_ORDER[a.session_type] - SESSION_ORDER[b.session_type]), [sessionsQ.data])

  useEffect(() => {
    if (!sessions.length || (sessionId !== null && sessions.some((s) => s.id === sessionId))) return
    const ready = sessions.filter((s) => s.ingestion.transforms)
    if (ready.length) setSession(ready[ready.length - 1].id)
  }, [sessions, sessionId, setSession])

  const ready = sessionId !== null && sessions.some((s) => s.id === sessionId)
  const headline = useFetch((s) => api.headline(sessionId!, s), [sessionId, ready], ready)
  const detail = useFetch((s) => api.detail(sessionId!, undefined, s), [sessionId, ready], ready)
  const anns = useFetch((s) => api.chartAnnotations(sessionId!, s), [sessionId, ready], ready)
  const spot = useFetch((s) => api.midfieldSpotlight(sessionId!, false, s), [sessionId, ready], ready)
  const moments = useFetch((s) => api.pivotalMoments(sessionId!, s), [sessionId, ready], ready)

  // drop selected drivers who didn't take part in this session
  useEffect(() => {
    if (!headline.data || sessionId === null) return
    const rows = headline.data.practice ?? headline.data.qualifying ?? headline.data.race ?? []
    const present = new Set(rows.map((r) => r.driver_id))
    if (driverIds.some((d) => !present.has(d))) setSession(sessionId, present)
  }, [headline.data, sessionId, driverIds, setSession])

  const drivers = headline.data?.drivers ?? {}
  const selected: Driver[] = driverIds.map((id) => drivers[String(id)]).filter(Boolean)
  const colors = slotColors(selected.map((d) => d.team))
  const session = sessions.find((s) => s.id === sessionId)
  const mapIdx = Math.min(mapDriver, Math.max(0, selected.length - 1))
  const mapFor = selected[mapIdx]

  const turnDeltas = useFetch((s) => api.turnDeltas(sessionId!, mapFor!.id, s), [sessionId, mapFor?.id, ready], ready && !!mapFor)
  const turnTiers = useMemo(() => turnDeltas.data && !turnDeltas.data.is_reference_lap ? Object.fromEntries(turnDeltas.data.turns.map((t) => [t.number, turnTier(t.delta_ms)])) as Record<number, Tier> : undefined, [turnDeltas.data])

  // per-sector: each driver's best delta to the session best, the field average, and the holder
  const sectors = useMemo(() => {
    const out = ([1, 2, 3] as const).map((sec) => {
      const best = new Map<number, number>()
      let bestMs: number | null = null, holder: number | null = null
      for (const d of detail.data?.sector_deltas ?? []) {
        if (d.sector !== sec || d.delta_ms === null) continue
        if ((best.get(d.driver_id) ?? Infinity) > d.delta_ms) best.set(d.driver_id, d.delta_ms)
        if (d.delta_ms === 0) { bestMs = d.session_best_sector_ms; holder = d.driver_id }
      }
      const vals = [...best.values()]
      return { sec, best, avg: vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null, bestMs, holder }
    })
    return out
  }, [detail.data])
  const tiers: [Tier, Tier, Tier] | undefined = detail.data?.sector_deltas.length
    ? (sectors.map((s) => (mapFor ? sectorTier(s.best.get(mapFor.id), s.avg) : 'purple')) as [Tier, Tier, Tier])
    : undefined

  const fastest = useMemo(() => {
    let best: { id: number; ms: number } | undefined
    for (const r of detail.data?.degradation ?? []) if (r.lap_time_ms && (!best || r.lap_time_ms < best.ms)) best = { id: r.driver_id, ms: r.lap_time_ms }
    return best
  }, [detail.data])
  const pick = (id: number) => { clearDrivers(); toggleDriver(id) }
  const tiles = headline.data ? tilesFor(headline.data, spot.data, pick, fastest) : []

  return (
    <div className="wrap pt-8">
      <nav className="label mb-3" aria-label="Breadcrumb">
        <Link to="/" className="hover:text-[var(--text)]">{event.data?.season_year ?? ''} season</Link>
        <span className="mx-2">/</span>
        <span>Round {event.data?.round ?? ''}</span>
      </nav>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-7">
        <div>
          <h1 className="h-feature">{event.data?.name ?? ' '}</h1>
          <p className="t2 mt-2 text-[13px]">{event.data && [event.data.circuit_name, event.data.country, shortDate(event.data.event_date)].filter(Boolean).join(' · ')}</p>
        </div>
        <div className="seg" role="tablist" aria-label="Session">
          {sessions.map((s) => (
            <button key={s.id} role="tab" aria-pressed={s.id === sessionId} aria-selected={s.id === sessionId} disabled={!s.ingestion.transforms} onClick={() => setSession(s.id)}>
              {SESSION_SHORT[s.session_type as SessionType]}
            </button>
          ))}
        </div>
      </div>

      {sessions.length > 0 && !sessions.some((s) => s.ingestion.transforms) && <div className="panel p-8 text-center t2">No sessions processed for this event yet.</div>}

      {headline.data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          {tiles.map((t) => <Tile key={t.label} t={t} />)}
        </div>
      )}

      {ready && (
        <div className="grid lg:grid-cols-12 gap-4 items-stretch">
          <section className="panel lg:col-span-5 flex flex-col" aria-label="Classification">
            <div className="panel-head pb-2">
              <h2 className="h2">Classification</h2>
              {selected.length > 0 ? <button className="btn-ghost text-[12px]" onClick={clearDrivers}>Clear selection</button> : <span className="label">Select up to two drivers</span>}
            </div>
            <div className="px-1.5 pb-1.5 overflow-x-auto">
              {headline.data ? <Classification headline={headline.data} selected={driverIds} colors={colors} onSelect={toggleDriver} /> : <div className="skeleton h-[600px] m-2" />}
            </div>
          </section>

          <div className="lg:col-span-7 flex flex-col gap-4">
          <section className="panel flex-1 flex flex-col" aria-label="Circuit">
            <div className="panel-head">
              <h2 className="h2">{mapFor ? `${mapFor.name} · sectors and corners` : 'Fastest sectors'}</h2>
              {selected.length === 2 && (
                <div className="seg sm">{selected.map((d, i) => <button key={d.id} aria-pressed={i === mapIdx} onClick={() => setMapDriver(i)}>{d.code}</button>)}</div>
              )}
            </div>
            <div className="flex-1 flex items-center justify-center px-3 sm:px-6 py-4 min-h-[220px] sm:min-h-[340px]">
              {outline.data ? <TrackMap outline={outline.data} sectors={tiers} turns={turnTiers} showTurns stroke={11} className="w-full max-h-[460px]" /> : <span className="label">{outline.loading ? '' : 'Circuit map unavailable'}</span>}
            </div>
            <div className="grid grid-cols-3 border-t" style={{ borderColor: 'var(--line)' }}>
              {sectors.map((s, i) => {
                const mine = mapFor ? s.best.get(mapFor.id) : undefined
                const t: Tier = tiers?.[i] ?? 'none'
                return (
                  <div key={s.sec} className={`px-4 py-3 ${i ? 'border-l' : ''}`} style={{ borderColor: 'var(--line)' }}>
                    <div className="flex items-center gap-2 label"><span className="dot" style={{ background: TIER_COLOR[t] }} />Sector {s.sec}</div>
                    <div className="text-[16px] font-semibold num mt-1">
                      {mapFor ? (mine === undefined ? '–' : mine <= 15 ? 'Fastest' : `+${fmtMs(mine)}s`) : s.bestMs ? fmtMs(s.bestMs) : '–'}
                    </div>
                    <div className="text-[12px] t3 mt-0.5 truncate">{mapFor ? TIER_LABEL[t] : s.holder ? drivers[String(s.holder)]?.name : ''}</div>
                  </div>
                )
              })}
            </div>
          </section>
          {moments.data && <KeyMoments moments={moments.data} drivers={drivers} onPick={pick} />}
          </div>
        </div>
      )}

      {ready && selected.length === 0 && spot.data && (
        <div className="mt-4"><BeyondPodium spot={spot.data} drivers={drivers} onPick={pick} /></div>
      )}

      {ready && isRaceLike(session?.session_type) && detail.data && (
        <section className="panel mt-4" aria-label="Race positions">
          <div className="panel-head">
            <h2 className="h2">Positions by lap</h2>
            <span className="label">{selected.length ? 'Circles mark pit stops' : 'Hover a line, click to select'}</span>
          </div>
          <div className="panel-body pt-2">
            <PositionChart rows={detail.data.position_by_lap} drivers={drivers} selected={driverIds} annotations={anns.data ?? []} pitStops={detail.data.pit_stops} stints={detail.data.stint_timeline} onSelect={toggleDriver} />
          </div>
        </section>
      )}

      {ready && sessionId !== null && (
        <div className="mt-4 space-y-4">
          {selected.length === 2 && headline.data && <CompareView eventId={eventId} sessionId={sessionId} headline={headline.data} a={selected[0]} b={selected[1]} colors={colors} />}
          {selected.map((d, i) => <DriverStory key={d.id} eventId={eventId} sessionId={sessionId} sessions={sessions} driver={d} color={colors[i]} onSession={setSession} />)}
          {detail.data && headline.data && session && <DeepDive sessionType={session.session_type} sessionId={sessionId} detail={detail.data} headline={headline.data} selected={selected} />}
        </div>
      )}
    </div>
  )
}

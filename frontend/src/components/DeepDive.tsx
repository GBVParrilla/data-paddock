import { useState } from 'react'
import { api, fmtMs, type Detail, type Driver, type Headline } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { isRaceLike, tyre, TYRE, turnTier, TIER_COLOR, UNKNOWN_TYRE } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { Term } from './Glossary'
import { TierLegend } from './race/CircuitPanel'
import { IncidentTimeline } from './race/IncidentTimeline'

type Tab = 'tyres' | 'turns' | 'sectors' | 'pace' | 'incidents'

function order(h: Headline): number[] {
  const rows = (h.race ?? []).map((r) => [r.driver_id, r.classification_order ?? r.finish_position ?? 99] as const)
    .concat((h.qualifying ?? []).map((r) => [r.driver_id, r.position ?? 99] as const))
    .concat((h.practice ?? []).map((r) => [r.driver_id, r.rank ?? 99] as const))
  return [...rows].sort((x, y) => x[1] - y[1]).map((r) => r[0])
}

function TyreStrategy({ detail, headline, selected }: { detail: Detail; headline: Headline; selected: number[] }) {
  const maxLap = Math.max(1, ...detail.stint_timeline.map((s) => s.lap_end ?? 0))
  const ids = order(headline).filter((id) => detail.stint_timeline.some((s) => s.driver_id === id))
  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <span className="label"><Term k="compound">Tyres</Term></span>
        {Object.entries(TYRE).map(([k, t]) => detail.stint_timeline.some((s) => s.compound === k) && (
          <span key={k} className="flex items-center gap-1.5 text-[12px] t2"><span className="dot" style={{ background: t.color }} />{t.label}</span>
        ))}
        {detail.stint_timeline.some((s) => !s.compound || !TYRE[s.compound]) && (
          <span className="flex items-center gap-1.5 text-[12px] t2" title="The timing feed didn't report this compound"><span className="dot" style={{ background: UNKNOWN_TYRE.color }} />Unknown (not in the feed)</span>
        )}
      </div>
      <div className="space-y-[5px]">
        {ids.map((id) => {
          const d = headline.drivers[String(id)]
          const on = selected.includes(id)
          return (
            <div key={id} className="grid grid-cols-[2.5rem_1fr] items-center gap-2" style={{ opacity: selected.length && !on ? 0.45 : 1 }}>
              <span className={`text-[12px] num ${on ? 'font-semibold' : 't2'}`}>{d?.code}</span>
              <div className="relative h-[13px]">
                {detail.stint_timeline.filter((s) => s.driver_id === id).map((s) => {
                  const a = s.lap_start ?? 1, b = s.lap_end ?? a, t = tyre(s.compound)
                  return <div key={s.stint_number} title={`${d?.code} · ${t.label} · laps ${a}–${b}`} className="absolute top-0 h-full rounded-[3px]"
                    style={{ left: `${((a - 1) / maxLap) * 100}%`, width: `calc(${((b - a + 1) / maxLap) * 100}% - 2px)`, background: t.color }} />
                })}
              </div>
            </div>
          )
        })}
      </div>
      <div className="grid grid-cols-[2.5rem_1fr] gap-2 mt-2"><span /><div className="flex justify-between label"><span>Lap 1</span><span>Lap {maxLap}</span></div></div>
    </div>
  )
}

function TurnByTurn({ sessionId, driver, headline }: { sessionId: number; driver: Driver; headline: Headline }) {
  const td = useFetch((s) => api.turnDeltas(sessionId, driver.id, s), [sessionId, driver.id])
  if (td.loading) return <div className="skeleton h-40" />
  if (td.error) return <p className="t2">{td.error.message}</p>
  if (!td.data) return null
  const t = td.data
  const ref = headline.drivers[String(t.reference.driver_id)]
  if (t.is_reference_lap) return <p className="t2">{driver.name}'s lap {t.lap_number} was the fastest of the session: it is the <Term k="reference">reference lap</Term> everyone else is measured against.</p>
  const rest = t.unattributed_ms ?? 0
  const lim = Math.max(100, ...t.turns.map((x) => Math.abs(x.delta_ms)), Math.abs(rest))
  const bar = (key: string, label: string, ms: number, color: string, title?: string) => {
    const w = (Math.abs(ms) / lim) * 50
    return (
      <div key={key} className="grid grid-cols-[3.5rem_1fr_4.5rem] items-center gap-2 h-6">
        <span className="text-[12px] t2 num">{label}</span>
        <div className="relative h-full">
          <div className="absolute top-0 bottom-0 left-1/2 w-px" style={{ background: 'var(--line-2)' }} />
          <div className="absolute top-[5px] bottom-[5px] rounded-[3px]" title={title} style={{ background: color, left: ms < 0 ? `${50 - w}%` : '50%', width: `${Math.max(w, 0.4)}%` }} />
        </div>
        <span className="text-[12px] num text-right">{ms > 0 ? '+' : ''}{(ms / 1000).toFixed(3)}</span>
      </div>
    )
  }
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 mb-4">
        <div><span className="label">{driver.code} best lap</span> <span className="num font-semibold">{fmtMs(t.lap_time_ms ?? null)}</span> <span className="label">lap {t.lap_number}</span></div>
        <div><span className="label">vs <Term k="reference">reference</Term> ({ref?.code ?? '–'}, lap {t.reference.lap_number})</span> <span className="num font-semibold">{fmtMs(t.reference.lap_time_ms ?? null)}</span></div>
        <div><span className="label">Total</span> <span className="num font-semibold">{t.total_lap_delta_ms > 0 ? '+' : ''}{(t.total_lap_delta_ms / 1000).toFixed(3)}s</span></div>
      </div>
      <div className="space-y-1">
        {t.turns.map((x) => bar(String(x.number), `T${x.number}`, x.delta_ms, TIER_COLOR[turnTier(x.delta_ms)], `${x.apex_speed_kph.toFixed(0)} km/h apex${x.from_m != null ? ` · ${Math.round(x.from_m)}–${Math.round(x.to_m ?? 0)} m` : ''}`))}
        {bar('rest', 'Other', rest, 'var(--none)', 'Timing that telemetry sampling can\'t place on a corner')}
      </div>
      <div className="grid grid-cols-[3.5rem_1fr_4.5rem] gap-2 mt-2 label"><span /><div className="flex justify-between"><span>Gained</span><span>Lost</span></div><span /></div>
      <p className="label mt-3">Each corner covers the track from halfway after the previous corner to halfway before the next, so the rows add up to the total. "Other" is what the timing loops measured but the position telemetry can't place.</p>
      <div className="mt-3"><TierLegend turns /></div>
    </div>
  )
}

function Sectors({ detail, headline, driver }: { detail: Detail; headline: Headline; driver: Driver }) {
  const rows = ([1, 2, 3] as const).map((sec) => {
    const per = new Map<number, number>()
    let best: number | null = null
    for (const d of detail.sector_deltas) {
      if (d.sector !== sec || d.driver_sector_ms === null) continue
      per.set(d.driver_id, Math.min(per.get(d.driver_id) ?? Infinity, d.driver_sector_ms))
      if (d.session_best_sector_ms !== null) best = d.session_best_sector_ms
    }
    const ranked = [...per.entries()].sort((x, y) => x[1] - y[1])
    const idx = ranked.findIndex(([id]) => id === driver.id)
    const holder = ranked[0] ? headline.drivers[String(ranked[0][0])] : undefined
    return { sec, mine: per.get(driver.id), best: best ?? ranked[0]?.[1], rank: idx >= 0 ? idx + 1 : null, of: ranked.length, holder }
  })
  return (
    <table className="tbl">
      <thead><tr><th>Sector</th><th className="r">{driver.code} best</th><th className="r">Gap</th><th className="r">Rank</th><th className="r">Session best</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.sec}>
            <td className="t2">Sector {r.sec}</td>
            <td className="r num">{fmtMs(r.mine)}</td>
            <td className="r num t2">{r.mine !== undefined && r.best !== undefined ? (r.mine - r.best === 0 ? 'Best' : `+${fmtMs(r.mine - r.best)}`) : '–'}</td>
            <td className="r num t2">{r.rank ? `${r.rank} / ${r.of}` : '–'}</td>
            <td className="r num t2">{fmtMs(r.best)} <span className="t3">{r.holder?.code}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function LongRunPace({ detail, headline, selected }: { detail: Detail; headline: Headline; selected: number[] }) {
  const compounds = [...new Set(detail.long_run_pace.map((r) => r.compound))].sort((a, b) => Object.keys(TYRE).indexOf(a) - Object.keys(TYRE).indexOf(b))
  const [c, setC] = useState(compounds[0])
  const cur = compounds.includes(c) ? c : compounds[0]
  if (!cur) return <p className="t2">No long runs in this session.</p>
  const rows = detail.long_run_pace.filter((r) => r.compound === cur).sort((a, b) => a.avg_lap_time_ms - b.avg_lap_time_ms)
  const best = rows[0]?.avg_lap_time_ms ?? 0
  const worst = rows[rows.length - 1]?.avg_lap_time_ms ?? best + 1
  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <div className="seg sm">{compounds.map((k) => <button key={k} aria-pressed={k === cur} onClick={() => setC(k)}>{tyre(k).label}</button>)}</div>
        <span className="label">Average lap on runs of 5+ laps. Under 8 laps is a small sample; fuel loads aren't known.</span>
      </div>
      <div className="space-y-1">
        {rows.map((r) => {
          const d = headline.drivers[String(r.driver_id)]
          const on = selected.includes(r.driver_id)
          const w = 8 + ((r.avg_lap_time_ms - best) / Math.max(1, worst - best)) * 92
          return (
            <div key={r.driver_id} className="grid grid-cols-[2.5rem_1fr_5rem_4rem] items-center gap-2 h-6" style={{ opacity: selected.length && !on ? 0.5 : 1 }}>
              <span className={`text-[12px] ${on ? 'font-semibold' : 't2'}`}>{d?.code}</span>
              <div className="h-[10px] rounded-[3px]" style={{ width: `${w}%`, background: teamColor(d?.team), opacity: 0.85 }} />
              <span className="text-[12px] num text-right">{fmtMs(r.avg_lap_time_ms)}</span>
              <span className={`text-[12px] num text-right ${r.lap_count < 8 ? 't3 italic' : 't3'}`} title={r.lap_count < 8 ? 'Small sample' : undefined}>{r.lap_count} laps</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** `turnsFor`: drivers with a turn-by-turn breakdown (static site), or null when the live API computes them on request. */
export function DeepDive({ sessionType, sessionId, detail, headline, selected, turnsFor }: { sessionType: string; sessionId: number; detail: Detail; headline: Headline; selected: Driver[]; turnsFor?: number[] | null }) {
  // an empty tab is worse than none (REVIEW #8 / ROUND2 #41): show it only for a driver who has a breakdown
  const withTurns = selected.filter((d) => !turnsFor || turnsFor.includes(d.id))
  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: 'tyres', label: 'Tyre strategy', show: detail.stint_timeline.length > 0 },
    { id: 'pace', label: 'Long-run pace', show: detail.long_run_pace.length > 0 && !isRaceLike(sessionType) },
    { id: 'sectors', label: 'Sectors', show: selected.length > 0 },
    { id: 'turns', label: 'Turn by turn', show: withTurns.length > 0 },
    { id: 'incidents', label: 'Race control', show: true },
  ]
  const visible = tabs.filter((t) => t.show)
  const [tab, setTab] = useState<Tab>('tyres')
  const cur = visible.find((t) => t.id === tab) ? tab : visible[0]?.id
  if (!cur) return null
  const ids = selected.map((d) => d.id)
  return (
    <section aria-label="Deep dive">
      <div className="px-5 pt-3">
        <div className="tabs overflow-x-auto" role="tablist">
          {visible.map((t) => <button key={t.id} role="tab" aria-selected={t.id === cur} onClick={() => setTab(t.id)}>{t.label}</button>)}
        </div>
      </div>
      <div className="px-5 py-5">
        {cur === 'tyres' && <TyreStrategy detail={detail} headline={headline} selected={ids} />}
        {cur === 'pace' && <LongRunPace detail={detail} headline={headline} selected={ids} />}
        {cur === 'sectors' && <div className="grid gap-6">{selected.map((d) => <Sectors key={d.id} detail={detail} headline={headline} driver={d} />)}</div>}
        {cur === 'incidents' && <IncidentTimeline sessionId={sessionId} headline={headline} selected={ids} />}
        {cur === 'turns' && <div className={`grid gap-8 ${withTurns.length === 2 ? 'lg:grid-cols-2' : ''}`}>{withTurns.map((d) => <div key={d.id}><div className="h2 mb-2">{d.name}</div><TurnByTurn sessionId={sessionId} driver={d} headline={headline} /></div>)}</div>}
      </div>
    </section>
  )
}

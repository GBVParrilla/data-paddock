import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartAnnotation, Driver, HeadlineRace, PitStopRow, PositionByLap, StintRow } from '../api/client'
import { tyre } from '../lib/f1'
import { slotColors, teamColor } from '../lib/teamColors'

const Y_W = 34
const R_PAD = 44
// Under a red flag the field queues in the pit lane; OpenF1 logs that as a "stop" of many minutes.
const SUSPENSION_LANE_MS = 120_000

/** Safety car / VSC / red flag periods from the key moments, as lap ranges. */
function neutralisations(anns: ChartAnnotation[]): { from: number; to: number; label: string }[] {
  return anns
    .filter((a) => (a.moment_type === 'safety_car' || a.moment_type === 'vsc' || a.moment_type === 'red_flag') && a.lap_number !== null)
    .map((a) => {
      const from = a.lap_number!
      const to = a.end_lap ?? from
      return { from, to: Math.max(to, from + 0.6), label: a.label }
    })
}

/** The second car of each team (in finishing order) is drawn dashed, so teammates never share a look. */
function dashedIds(race: HeadlineRace[], drivers: Record<string, Driver>): Set<number> {
  const seen = new Set<string>()
  const out = new Set<number>()
  for (const r of race) {
    const team = drivers[String(r.driver_id)]?.team ?? ''
    if (seen.has(team)) out.add(r.driver_id)
    seen.add(team)
  }
  return out
}

/**
 * Lap-by-lap running order. With no driver selected every car is drawn in its team colour;
 * selecting drivers brings them forward (others fade) and adds their pit stops and tyre stints.
 */
export function PositionChart({ rows, drivers, race, selected, annotations, pitStops: allStops, stints, onSelect }: {
  rows: PositionByLap[]
  drivers: Record<string, Driver>
  race: HeadlineRace[]
  selected: number[]
  annotations: ChartAnnotation[]
  pitStops: PitStopRow[]
  stints: StintRow[]
  onSelect: (id: number) => void
}) {
  const [hover, setHover] = useState<number | null>(null)
  const pitStops = useMemo(() => allStops.filter((p) => !(p.lane_duration_ms && p.lane_duration_ms >= SUSPENSION_LANE_MS)), [allStops])
  const dashed = useMemo(() => dashedIds(race, drivers), [race, drivers])
  const gridSize = Math.max(race.length, 1)
  const { data, ids, maxLap, maxPos, last } = useMemo(() => {
    const byLap = new Map<number, Record<string, number>>()
    const lastPos = new Map<number, { lap: number; pos: number }>()
    let maxLap = 1, maxPos = 1
    for (const r of rows) {
      if (r.position === null) continue
      const row = byLap.get(r.lap_number) ?? { lap: r.lap_number }
      row[`d${r.driver_id}`] = r.position
      byLap.set(r.lap_number, row)
      maxLap = Math.max(maxLap, r.lap_number)
      maxPos = Math.max(maxPos, r.position)
      const l = lastPos.get(r.driver_id)
      if (!l || r.lap_number > l.lap) lastPos.set(r.driver_id, { lap: r.lap_number, pos: r.position })
    }
    return { data: [...byLap.values()].sort((a, b) => a.lap - b.lap), ids: [...lastPos.keys()], maxLap, maxPos, last: lastPos }
  }, [rows])

  const selColors = slotColors(selected.map((id) => drivers[String(id)]?.team))
  const colorOf = (id: number) => {
    const i = selected.indexOf(id)
    return i !== -1 ? selColors[i] : teamColor(drivers[String(id)]?.team)
  }
  const focus = selected.length ? selected : hover !== null ? [hover] : []
  const ordered = [...ids.filter((id) => !focus.includes(id)), ...focus]
  const pos = (id: number, lap: number) => data.find((d) => d.lap === lap)?.[`d${id}`]
  const sc = neutralisations(annotations)

  return (
    <div>
      <div className="h-[340px]">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 18, right: R_PAD, bottom: 4, left: 0 }} onMouseLeave={() => setHover(null)}>
            <CartesianGrid stroke="var(--rule)" strokeDasharray="1 3" vertical={false} />
            {sc.map((s, i) => (
              <ReferenceArea key={i} x1={s.from} x2={s.to} fill="var(--yellow)" fillOpacity={0.07} stroke="none" ifOverflow="hidden"
                label={{ value: s.label, position: 'insideTop', fill: 'var(--text-3)', fontSize: 10, dy: -14 }} />
            ))}
            <XAxis dataKey="lap" type="number" domain={[1, maxLap]} tickCount={Math.min(12, maxLap)} allowDecimals={false} tick={{ fill: 'var(--text-2)', fontSize: 11 }} stroke="var(--ink)" tickLine={false} />
            <YAxis reversed domain={[1, Math.max(maxPos, gridSize)]} ticks={[1, 5, 10, 15, 20, Math.max(maxPos, gridSize)].filter((t, i, a) => t <= Math.max(maxPos, gridSize) && a.indexOf(t) === i)} width={Y_W} tick={{ fill: 'var(--text-2)', fontSize: 11 }} stroke="var(--ink)" tickLine={false} axisLine={false} tickFormatter={(v) => `P${v}`} />
            <Tooltip
              cursor={{ stroke: 'var(--line-2)' }}
              isAnimationActive={false}
              content={({ active, label }) => {
                if (!active || label === undefined) return null
                const lap = Number(label)
                const show = focus.length ? focus : []
                const pits = pitStops.filter((p) => p.lap_number === lap && show.includes(p.driver_id))
                return (
                  <div className="tip min-w-[140px]">
                    <div className="label mb-1">Lap {lap}</div>
                    {show.length === 0 && <div className="t3">Hover or select a driver</div>}
                    {show.map((id) => (
                      <div key={id} className="flex items-center gap-2 num">
                        <span className="dot" style={{ background: colorOf(id) }} />
                        <span className="font-medium w-9">{drivers[String(id)]?.code}</span>
                        <span className="t2">{pos(id, lap) !== undefined ? `P${pos(id, lap)}` : '–'}</span>
                      </div>
                    ))}
                    {pits.map((p) => <div key={p.driver_id} className="t2 mt-1">{drivers[String(p.driver_id)]?.code} pitted{p.duration_ms ? `, ${(p.duration_ms / 1000).toFixed(1)}s` : ''}</div>)}
                  </div>
                )
              }}
            />
            {ordered.map((id) => {
              const on = focus.includes(id)
              const dim = focus.length > 0 && !on
              const pitLaps = new Set(pitStops.filter((p) => p.driver_id === id).map((p) => p.lap_number))
              return (
                <Line
                  key={id}
                  dataKey={`d${id}`}
                  type="linear"
                  stroke={dim ? 'var(--line-2)' : colorOf(id)}
                  strokeOpacity={dim ? 0.7 : on ? 1 : 0.75}
                  strokeWidth={on ? 2.5 : 1.25}
                  // the driver picked is solid; who they're compared with is dashed (REVIEW_ROUND3 D8)
                  strokeDasharray={selected.length === 2 ? (id === selected[1] ? '6 3' : id === selected[0] ? undefined : dashed.has(id) ? '4 3' : undefined) : dashed.has(id) ? (on ? '6 3' : '4 3') : undefined}
                  isAnimationActive={false}
                  connectNulls
                  activeDot={false}
                  onMouseEnter={() => !selected.length && setHover(id)}
                  onClick={() => onSelect(id)}
                  style={{ cursor: 'pointer' }}
                  dot={(p: { cx?: number; cy?: number; payload?: { lap: number }; index?: number }) => {
                    const key = `${id}-${p.index}`
                    if (p.cx === undefined || p.cy === undefined || !p.payload) return <g key={key} />
                    const lap = p.payload.lap
                    // pit stops: only for drivers you've selected
                    if (selected.includes(id) && pitLaps.has(lap)) {
                      return <circle key={key} cx={p.cx} cy={p.cy} r={4.5} fill="var(--bg)" stroke={colorOf(id)} strokeWidth={2}><title>{`${drivers[String(id)]?.code} pit stop, lap ${lap}`}</title></circle>
                    }
                    // end label
                    if (lap === last.get(id)?.lap && !dim) {
                      return <text key={key} x={p.cx + 6} y={p.cy + 4} fontSize={10.5} fontWeight={on ? 600 : 500} fill={on ? 'var(--text)' : 'var(--text-2)'}>{drivers[String(id)]?.code}</text>
                    }
                    return <g key={key} />
                  }}
                />
              )
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {selected.length > 0 && (
        <div className="mt-2 space-y-1.5" style={{ paddingLeft: Y_W, paddingRight: R_PAD }}>
          {selected.map((id) => {
            const own = stints.filter((s) => s.driver_id === id).sort((a, b) => a.stint_number - b.stint_number)
            return (
              <div key={id} className="relative h-[14px] flex" aria-label={`${drivers[String(id)]?.code} tyre stints`}>
                <span className="absolute -left-[34px] text-[10.5px] font-medium t2 leading-[14px]">{drivers[String(id)]?.code}</span>
                {own.map((s) => {
                  const a = s.lap_start ?? 1, b = s.lap_end ?? a
                  const t = tyre(s.compound)
                  return (
                    <div key={s.stint_number} title={`${t.label} · laps ${a}–${b}`} className="h-full text-[9px] font-bold flex items-center justify-center text-[var(--ink)]" data-tyre
                      style={{ position: 'absolute', left: `${((a - 1) / maxLap) * 100}%`, width: `calc(${((b - a + 1) / maxLap) * 100}% - 2px)`, background: t.color }}>
                      {(b - a + 1) / maxLap > 0.06 ? t.letter : ''}
                    </div>
                  )
                })}
              </div>
            )
          })}
          <div className="flex items-center gap-1.5 label pt-1">
            <svg width="11" height="11" viewBox="0 0 11 11" aria-hidden="true"><circle cx="5.5" cy="5.5" r="4" fill="var(--bg)" stroke="var(--text-2)" strokeWidth="1.8" /></svg>
            Pit stop
          </div>
        </div>
      )}
    </div>
  )
}

import { CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartAnnotation, Driver, PitStopRow, PositionByLap, StintRow } from '../api/client'

const COMPOUND_COLOR: Record<string, string> = { SOFT: 'var(--tyre-soft)', MEDIUM: 'var(--tyre-medium)', HARD: 'var(--tyre-hard)', INTERMEDIATE: 'var(--tyre-inter)', WET: 'var(--tyre-wet)' }
const COMPOUND_LETTER: Record<string, string> = { SOFT: 'S', MEDIUM: 'M', HARD: 'H', INTERMEDIATE: 'I', WET: 'W' }
const compoundColor = (c: string | null) => (c && COMPOUND_COLOR[c]) || '#5b5b57'
const compoundLetter = (c: string | null) => (c && COMPOUND_LETTER[c]) || '?'

function CompoundStrip({ driver, color, stints, maxLap }: { driver: Driver; color: string; stints: StintRow[]; maxLap: number }) {
  const ordered = [...stints].sort((a, b) => a.stint_number - b.stint_number)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="font-semibold w-16 truncate" style={{ color }}>{driver.code ?? driver.name}</span>
      <div className="flex-1 flex h-4 rounded overflow-hidden border" style={{ borderColor: 'var(--line)' }}>
        {ordered.map((s, i) => {
          const start = s.lap_start ?? 1
          const end = s.lap_end ?? start
          const width = Math.max(2, ((end - start + 1) / maxLap) * 100)
          return (
            <div key={i} className="flex items-center justify-center text-[9px] font-bold" style={{ width: `${width}%`, background: compoundColor(s.compound), color: s.compound === 'HARD' ? '#111' : '#111' }} title={`${s.compound ?? 'Unknown'} · laps ${start}-${end}`}>
              {compoundLetter(s.compound)}
            </div>
          )
        })}
      </div>
      <span className="faint w-8 text-right">{ordered.length} stop{ordered.length === 1 ? '' : 's'}</span>
    </div>
  )
}

export function PositionChart({
  rows,
  drivers,
  highlighted,
  highlightColors,
  annotations,
  pitStops,
  stints,
}: {
  rows: PositionByLap[]
  drivers: Record<string, Driver>
  highlighted: number[]
  highlightColors: string[]
  annotations: ChartAnnotation[]
  pitStops: PitStopRow[]
  stints: StintRow[]
}) {
  const byLap = new Map<number, Record<string, number>>()
  const driverIds = new Set<number>()
  let maxPos = 1
  let maxLap = 1
  for (const r of rows) {
    if (r.position === null) continue
    driverIds.add(r.driver_id)
    maxPos = Math.max(maxPos, r.position)
    maxLap = Math.max(maxLap, r.lap_number)
    const row = byLap.get(r.lap_number) ?? { lap: r.lap_number }
    row[`d${r.driver_id}`] = r.position
    byLap.set(r.lap_number, row)
  }
  const data = [...byLap.values()].sort((a, b) => a.lap - b.lap)
  const pitCountByDriver = new Map<number, number>()
  for (const p of pitStops) pitCountByDriver.set(p.driver_id, (pitCountByDriver.get(p.driver_id) ?? 0) + 1)

  // Background context lines are limited to drivers who never pitted - pit-stop dips are just clutter
  // until you actually pick that driver. A selected driver always shows in full, pit stops and all.
  const backgroundIds = [...driverIds].filter((id) => !highlighted.includes(id) && !pitCountByDriver.get(id))
  const shownIds = [...backgroundIds, ...highlighted]
  const hiddenForPits = driverIds.size - shownIds.length

  // Pit-stop pivotal moments are only shown for a driver you've actually selected - your own
  // selected driver's pit stops get their own dedicated markers below anyway. Other pivotal-moment
  // types (safety car, penalties, position swings, fastest lap) still always show - those are the
  // session's story, not per-driver clutter.
  const lapAnns = annotations.filter((a) => a.lap_number !== null && (a.moment_type !== 'pit_stop' || highlighted.includes(a.driver_id!)))
  const posAt = (driverId: number, lap: number) => byLap.get(lap)?.[`d${driverId}`]

  return (
    <div className="w-full">
      <div className="h-80">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" type="number" domain={['dataMin', 'dataMax']} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} stroke="var(--line)" label={{ value: 'Lap', position: 'insideBottomRight', fill: 'var(--text-muted)', fontSize: 11, dy: 8 }} />
            <YAxis reversed domain={[1, maxPos]} allowDecimals={false} width={32} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} stroke="var(--line)" tickFormatter={(v) => `P${v}`} />
            <Tooltip
              cursor={{ stroke: 'var(--text-muted)', strokeWidth: 1 }}
              content={({ active, label }) => {
                if (!active || label === undefined) return null
                const lap = Number(label)
                const row = byLap.get(lap)
                const anns = lapAnns.filter((a) => a.lap_number === lap)
                return (
                  <div className="card px-3 py-2 text-xs shadow max-w-xs" style={{ background: 'var(--surface-1)' }}>
                    <div className="font-semibold mb-1">Lap {lap}</div>
                    {highlighted.map((id, i) => (
                      <div key={id} className="flex items-center gap-2">
                        <span className="inline-block w-3 h-1 rounded" style={{ background: highlightColors[i] }} />
                        {drivers[String(id)]?.name ?? id}: {row?.[`d${id}`] !== undefined ? `P${row[`d${id}`]}` : '–'}
                      </div>
                    ))}
                    {anns.map((a, i) => (
                      <div key={i} className="mt-1 pt-1 border-t" style={{ borderColor: 'var(--line)' }}>
                        <span className="font-semibold">{a.label}</span> <span className="muted">{a.description}</span>
                      </div>
                    ))}
                  </div>
                )
              }}
            />
            {shownIds.map((id) => {
              const hi = highlighted.indexOf(id)
              return (
                <Line key={id} type="monotone" dataKey={`d${id}`} name={drivers[String(id)]?.name ?? String(id)} stroke={hi === -1 ? 'var(--series-muted)' : highlightColors[hi]} strokeWidth={hi === -1 ? 1 : 3} dot={false} activeDot={hi === -1 ? false : { r: 4 }} isAnimationActive={false} connectNulls />
              )
            })}
            {highlighted.map((id, hi) =>
              (pitStops.filter((p) => p.driver_id === id)).map((p, j) => {
                const lap = p.lap_number
                const pos = posAt(id, lap) ?? posAt(id, lap + 1)
                if (pos === undefined) return null
                return (
                  <ReferenceDot key={`pit-${id}-${j}`} x={lap} y={pos} r={6} fill="var(--status-warning)" stroke={highlightColors[hi]} strokeWidth={2} label={{ value: `PIT L${lap}`, position: 'bottom', fontSize: 10, fill: 'var(--status-warning)', fontWeight: 700 }} />
                )
              }),
            )}
            {lapAnns.map((a, i) => {
              const nth = lapAnns.slice(0, i).filter((o) => o.lap_number === a.lap_number).length
              const pos = nth % 2 === 0 ? 'top' : 'bottom'
              if (a.driver_id && posAt(a.driver_id, a.lap_number!) !== undefined) {
                return <ReferenceDot key={i} x={a.lap_number!} y={posAt(a.driver_id, a.lap_number!)!} r={5} fill={a.moment_type === 'penalty' ? 'var(--status-critical)' : 'var(--status-warning)'} stroke="var(--surface-1)" strokeWidth={2} label={{ value: a.label, position: pos, fontSize: 10, fill: 'var(--text-secondary)' }} />
              }
              return <ReferenceLine key={i} x={a.lap_number!} stroke="var(--status-warning)" strokeDasharray="4 3" label={{ value: a.label, position: nth % 2 === 0 ? 'insideTop' : 'insideBottom', fontSize: 10, fill: 'var(--text-secondary)' }} />
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="faint text-[11px] mt-1">
        Markers are the session's pivotal moments (data-detected). Grey lines are drivers who made zero pit stops, shown for context.
        {hiddenForPits > 0 && ` ${hiddenForPits} driver${hiddenForPits === 1 ? '' : 's'} with pit stops are hidden until you select them.`}
      </p>
      {highlighted.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t pt-2" style={{ borderColor: 'var(--line)' }}>
          <div className="text-[11px] uppercase tracking-wide faint">Tyre strategy</div>
          {highlighted.map((id, hi) => {
            const d = drivers[String(id)]
            if (!d) return null
            return <CompoundStrip key={id} driver={d} color={highlightColors[hi]} stints={stints.filter((s) => s.driver_id === id)} maxLap={maxLap} />
          })}
        </div>
      )}
    </div>
  )
}

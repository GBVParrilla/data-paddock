import { useRef, useState } from 'react'

/**
 * The gap between two drivers, lap by lap, drawn as one SVG path (#61): the vs strip sits near the top of a driver
 * page, and the charting library it used cost a 300ms task on a phone. Above the line, `aCode` is ahead. A tap or
 * click picks the lap under the pointer; arrow keys move along the laps when the chart has focus.
 */
export function GapChart({ points, aCode, bCode, color, lap, onLap }: {
  points: { lap: number; ms: number }[] // ms > 0: a ahead
  aCode: string; bCode: string; color: string; lap?: number | null; onLap?: (lap: number) => void
}) {
  const ref = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const W = 600, H = 112, L = 40, R = 8, T = 6, B = 18
  const first = points[0].lap, last = points[points.length - 1].lap
  const lim = Math.max(1000, ...points.map((p) => Math.abs(p.ms)))
  const x = (l: number) => L + ((l - first) / Math.max(1, last - first)) * (W - L - R)
  const y = (ms: number) => T + ((lim - ms) / (2 * lim)) * (H - T - B)
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.lap).toFixed(1)},${y(p.ms).toFixed(1)}`).join('')
  const ticks = [first, ...[0.25, 0.5, 0.75].map((f) => Math.round(first + f * (last - first))), last].filter((t, i, a) => a.indexOf(t) === i)
  const lapAt = (clientX: number) => {
    const box = ref.current!.getBoundingClientRect()
    const vx = ((clientX - box.left) / box.width) * W
    const l = Math.round(first + ((vx - L) / (W - L - R)) * (last - first))
    return points.reduce((best, p) => (Math.abs(p.lap - l) < Math.abs(best - l) ? p.lap : best), points[0].lap)
  }
  const shown = hover ?? lap ?? null
  const at = shown != null ? points.find((p) => p.lap === shown) : undefined
  const fmt = (ms: number) => `${Math.abs(ms / 1000).toFixed(1)}s`
  const step = (dir: number) => {
    const i = points.findIndex((p) => p.lap === (lap ?? hover ?? points[0].lap))
    const next = points[Math.min(points.length - 1, Math.max(0, i + dir))]
    if (next && onLap) onLap(next.lap)
  }
  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="w-full h-28" preserveAspectRatio="none" role="img" tabIndex={onLap ? 0 : undefined}
        aria-label={`Gap by lap, ${aCode} against ${bCode}: ${points.length} laps, largest gap ${fmt(lim)}`} data-gap-chart
        style={onLap ? { cursor: 'pointer' } : undefined}
        onPointerMove={(e) => setHover(lapAt(e.clientX))} onPointerLeave={() => setHover(null)}
        onClick={(e) => onLap?.(lapAt(e.clientX))}
        onKeyDown={(e) => { if (e.key === 'ArrowRight') { e.preventDefault(); step(1) } else if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1) } }}>
        {[lim, -lim].map((v) => <line key={v} x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--rule)" strokeDasharray="1 3" vectorEffect="non-scaling-stroke" />)}
        <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} stroke="var(--ink)" vectorEffect="non-scaling-stroke" />
        {lap != null && <line x1={x(lap)} x2={x(lap)} y1={T} y2={H - B} stroke="var(--ink)" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />}
        {hover != null && hover !== lap && <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke="var(--line-2)" vectorEffect="non-scaling-stroke" />}
        <path d={d} fill="none" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      </svg>
      {/* axis labels as HTML, so they keep their size when the SVG stretches */}
      <div className="absolute inset-y-0 left-0 w-10 flex flex-col justify-between text-[11px] t3 num pointer-events-none pb-4" aria-hidden="true">
        <span>+{(lim / 1000).toFixed(0)}s</span><span>0</span><span>-{(lim / 1000).toFixed(0)}s</span>
      </div>
      <div className="relative h-4 text-[11px] t2 num pointer-events-none" aria-hidden="true">
        {ticks.map((t) => <span key={t} className="absolute -translate-x-1/2" style={{ left: `${(x(t) / W) * 100}%` }}>{t}</span>)}
      </div>
      {at && (
        <div className="tip num absolute top-0 pointer-events-none" style={{ left: `min(calc(${(x(at.lap) / W) * 100}% + 8px), calc(100% - 9rem))` }}>
          <div className="label">Lap {at.lap}</div>{at.ms === 0 ? 'Level' : `${at.ms > 0 ? aCode : bCode} ahead by ${fmt(at.ms)}`}
        </div>
      )}
    </div>
  )
}

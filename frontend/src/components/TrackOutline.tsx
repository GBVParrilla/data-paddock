import { useMemo } from 'react'
import type { TrackOutline as Outline } from '../api/client'
import { fmtMs } from '../api/client'

export type SectorMode =
  | { kind: 'plain' }
  | { kind: 'session-best'; best: Record<1 | 2 | 3, { ms: number | null; holder: string | null }> }
  | { kind: 'driver'; label: string; deltas: Record<1 | 2 | 3, number | null>; avg: Record<1 | 2 | 3, number | null> }

type PerfTier = 'purple' | 'green' | 'yellow' | 'red' | 'none'

const TIER_COLOR: Record<PerfTier, string> = {
  purple: 'var(--perf-purple)',
  green: 'var(--perf-green)',
  yellow: 'var(--perf-yellow)',
  red: 'var(--perf-red)',
  none: 'var(--perf-muted)',
}
const TIER_LABEL: Record<PerfTier, string> = {
  purple: 'Fastest',
  green: 'Good (better than average)',
  yellow: 'Medium (near average)',
  red: 'Slower (worse than average)',
  none: 'No data',
}

/** F1 timing-screen convention: purple = outright fastest. Green/yellow/red graded against the field average. */
export function classifyDelta(delta: number | null, avg: number | null): PerfTier {
  if (delta === null || delta === undefined) return 'none'
  if (delta <= 15) return 'purple'
  if (avg === null || avg <= 0) return 'green'
  if (delta <= avg) return 'green'
  if (delta <= avg * 1.6) return 'yellow'
  return 'red'
}

/** Turn deltas use fixed thresholds (not field-relative like sectors) - there's no cheap way to get
 * every driver's turn deltas for a field average, so a per-turn "typical" scale is used instead. */
function turnTier(deltaMs: number | undefined): PerfTier {
  if (deltaMs === undefined) return 'none'
  if (deltaMs <= -30) return 'purple'
  if (deltaMs <= 60) return 'green'
  if (deltaMs <= 200) return 'yellow'
  return 'red'
}

function toPath(pts: [number, number][]): string {
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]} ${p[1]}`).join(' ')
}

/** Unit perpendicular direction at index i, estimated from neighbouring points (for tick marks). */
function perpAt(pts: [number, number][], i: number): [number, number] {
  const a = pts[Math.max(0, i - 2)]
  const b = pts[Math.min(pts.length - 1, i + 2)]
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const len = Math.hypot(dx, dy) || 1
  return [-dy / len, dx / len]
}

function SectorTick({ pts, index, length = 26 }: { pts: [number, number][]; index: number; length?: number }) {
  const [px, py] = pts[Math.min(index, pts.length - 1)]
  const [nx, ny] = perpAt(pts, index)
  return <line x1={px - nx * length} y1={py - ny * length} x2={px + nx * length} y2={py + ny * length} stroke="var(--text-primary)" strokeWidth={4} opacity={0.85} />
}

function TurnMarker({ pts, index, number, color }: { pts: [number, number][]; index: number; number: number; color: string }) {
  const [x, y] = pts[Math.min(index, pts.length - 1)]
  return (
    <g>
      <circle cx={x} cy={y} r={13} fill={color} stroke="var(--surface-1)" strokeWidth={2.5} />
      <text x={x} y={y + 4.5} textAnchor="middle" fontSize={13} fontWeight={800} fill="#0b0b0b">{number}</text>
      <title>{`Turn ${number}`}</title>
    </g>
  )
}

function StartFinishMarker({ pts, strokeWidth }: { pts: [number, number][]; strokeWidth: number }) {
  const [px, py] = pts[0]
  const [nx, ny] = perpAt(pts, 0)
  const angleDeg = (Math.atan2(ny, nx) * 180) / Math.PI
  const w = strokeWidth + 8
  const h = 10
  const cols = 6
  const cellW = w / cols
  return (
    <g transform={`translate(${px} ${py}) rotate(${angleDeg})`}>
      <rect x={-w / 2} y={-h / 2} width={w} height={h} fill="white" stroke="black" strokeWidth={1.5} />
      {Array.from({ length: cols }).map((_, i) => (i % 2 === 0 ? <rect key={i} x={-w / 2 + i * cellW} y={-h / 2} width={cellW} height={h / 2} fill="black" /> : null))}
      {Array.from({ length: cols }).map((_, i) => (i % 2 === 1 ? <rect key={`b${i}`} x={-w / 2 + i * cellW} y={0} width={cellW} height={h / 2} fill="black" /> : null))}
      <title>Start / finish line</title>
    </g>
  )
}

const ESRI_IMAGERY = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export'

export function TrackOutline({
  outline,
  mode,
  size = 320,
  showLegend = true,
  strokeWidth = 14,
  theme = 'track',
  satelliteRotationDeg = 0,
  satelliteMirror = false,
  turnDeltasMs,
}: {
  outline: Outline
  mode: SectorMode
  size?: number | string
  showLegend?: boolean
  strokeWidth?: number
  theme?: 'track' | 'satellite'
  satelliteRotationDeg?: number
  satelliteMirror?: boolean
  /** turn number -> delta_ms, to color the turn markers once a driver's turn-deltas have loaded */
  turnDeltasMs?: Record<number, number>
}) {
  const isSat = theme === 'satellite' && !!outline.geo_points && !!outline.geo_bbox
  const pts = isSat ? outline.geo_points! : outline.points
  const i1 = Math.min(outline.sector_1_end_index, pts.length - 1)
  const i2 = Math.min(Math.max(outline.sector_2_end_index, i1 + 1), pts.length - 1)
  const segs: [number, number][][] = [pts.slice(0, i1 + 1), pts.slice(i1, i2 + 1), [...pts.slice(i2), pts[0]]]

  const tier = (sec: 1 | 2 | 3): PerfTier => {
    if (mode.kind === 'plain') return 'none'
    if (mode.kind === 'session-best') return 'purple'
    return classifyDelta(mode.deltas[sec], mode.avg[sec])
  }
  const colors = ([1, 2, 3] as const).map((s) => TIER_COLOR[tier(s)])
  const mid = (seg: [number, number][]) => seg[Math.floor(seg.length / 2)]

  const satUrl = useMemo(() => {
    if (!isSat || !outline.geo_bbox) return null
    const { south, west, north, east } = outline.geo_bbox
    const params = new URLSearchParams({ bbox: `${west},${south},${east},${north}`, bboxSR: '4326', imageSR: '4326', size: '900,900', format: 'png32', f: 'image' })
    return `${ESRI_IMAGERY}?${params.toString()}`
  }, [isSat, outline.geo_bbox])

  const strokeOp = isSat ? 0.95 : 1
  const trackStroke = isSat ? Math.max(7, strokeWidth * 0.5) : strokeWidth
  // satellite overlay is a guess (unknown true-north alignment of the telemetry axes) - the caller
  // lets the viewer rotate/mirror it to match the photo, applied here as one SVG transform.
  const satTransform = isSat ? `translate(500 500) rotate(${satelliteRotationDeg}) scale(${satelliteMirror ? -1 : 1} 1) translate(-500 -500)` : undefined

  return (
    <div className="flex flex-col items-center gap-2 w-full">
      <div className="relative w-full" style={{ aspectRatio: '1 / 1', maxWidth: typeof size === 'number' ? size : undefined }}>
        {isSat && satUrl && (
          <img src={satUrl} alt="Satellite view of the circuit" className="absolute inset-0 w-full h-full object-cover rounded-lg" loading="lazy" />
        )}
        <svg viewBox="0 0 1000 1000" className="absolute inset-0 w-full h-full" role="img" aria-label="Track outline derived from car position telemetry">
          <g transform={satTransform}>
          {!isSat && <path d={toPath([...pts, pts[0]])} fill="none" stroke="var(--line)" strokeWidth={trackStroke + 6} strokeLinejoin="round" strokeLinecap="round" />}
          {isSat && <path d={toPath([...pts, pts[0]])} fill="none" stroke="#000000" strokeOpacity={0.85} strokeWidth={trackStroke + 8} strokeLinejoin="round" strokeLinecap="round" />}
          {isSat && <path d={toPath([...pts, pts[0]])} fill="none" stroke="#ffffff" strokeOpacity={0.9} strokeWidth={trackStroke + 4} strokeLinejoin="round" strokeLinecap="round" />}
          {segs.map((seg, i) => (
            <path key={i} d={toPath(seg)} fill="none" stroke={colors[i]} strokeOpacity={strokeOp} strokeWidth={trackStroke} strokeLinejoin="round" strokeLinecap="round">
              <title>{`Sector ${i + 1}`}</title>
            </path>
          ))}
          {outline.drs_zones.map(([a, b], i) => (
            <path key={`drs${i}`} d={toPath(pts.slice(a, b + 1))} fill="none" stroke="#39ff6a" strokeOpacity={0.95} strokeWidth={Math.max(3, trackStroke * 0.28)} strokeDasharray="10 8" strokeLinecap="round">
              <title>{outline.drs_zone_source === 'telemetry' ? 'Boost zone (DRS open)' : 'Estimated boost zone (sustained full throttle near top speed)'}</title>
            </path>
          ))}
          <SectorTick pts={pts} index={i1} length={isSat ? 16 : 26} />
          <SectorTick pts={pts} index={i2} length={isSat ? 16 : 26} />
          <StartFinishMarker pts={pts} strokeWidth={trackStroke} />
          {outline.turns.map((t) => (
            <TurnMarker key={t.number} pts={pts} index={t.index} number={t.number} color={turnDeltasMs ? TIER_COLOR[turnTier(turnDeltasMs[t.number])] : 'var(--surface-3)'} />
          ))}
          {mode.kind !== 'plain' &&
            !isSat &&
            segs.map((seg, i) => {
              const [x, y] = mid(seg)
              return (
                <g key={`l${i}`}>
                  <circle cx={x} cy={y} r={30} fill="var(--surface-1)" stroke="var(--line)" strokeWidth={3} />
                  <text x={x} y={y + 11} textAnchor="middle" fontSize={30} fontWeight={900} fill="var(--text-primary)">S{i + 1}</text>
                </g>
              )
            })}
          </g>
        </svg>
      </div>
      {showLegend && mode.kind === 'session-best' && (
        <div className="text-xs w-full">
          <div className="muted mb-1">Session-best sector times (purple = fastest, any driver)</div>
          <ul className="grid grid-cols-3 gap-2">
            {([1, 2, 3] as const).map((s) => (
              <li key={s} className="card px-2 py-1" style={{ borderTop: `2px solid var(--perf-purple)` }}>
                <span className="font-semibold">S{s}</span> <span className="font-mono">{fmtMs(mode.best[s].ms)}</span>
                <div className="faint truncate">{mode.best[s].holder ?? '—'}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {showLegend && mode.kind === 'driver' && (
        <div className="text-xs w-full">
          <div className="muted mb-1">{mode.label}: sector performance vs the field</div>
          <ul className="flex flex-wrap gap-x-3 gap-y-1">
            {(['purple', 'green', 'yellow', 'red'] as const).map((t) => (
              <li key={t} className="flex items-center gap-1">
                <span className="inline-block w-4 h-2 rounded-sm" style={{ background: TIER_COLOR[t] }} /> {TIER_LABEL[t]}
              </li>
            ))}
          </ul>
          <div className="grid grid-cols-3 gap-2 mt-2">
            {([1, 2, 3] as const).map((s) => (
              <div key={s} className="card px-2 py-1" style={{ borderTop: `2px solid ${TIER_COLOR[tier(s)]}` }}>
                <span className="font-semibold">S{s}</span> <span className="font-mono">{fmtMs(mode.deltas[s], true)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {showLegend && outline.drs_zones.length > 0 && (
        <p className="faint text-[11px] flex items-center gap-1.5">
          <span className="inline-block w-4 h-1 rounded" style={{ background: '#39ff6a' }} />
          Boost zones ({outline.drs_zone_source === 'telemetry' ? 'from DRS telemetry' : 'estimated from full-throttle straights — the API has no DRS signal for this session'})
        </p>
      )}
      {showLegend && isSat && <p className="faint text-[11px] text-center max-w-xs">Satellite imagery via Esri World Imagery. The overlay's rotation isn't measured - telemetry axes aren't documented to true north - use the controls below to line it up with the road.</p>}
      {showLegend && !isSat && <p className="faint text-[11px] text-center max-w-xs">Outline from one lap of car position data, rotated to run roughly landscape; sector splits are approximate (from that lap's sector times).</p>}
    </div>
  )
}

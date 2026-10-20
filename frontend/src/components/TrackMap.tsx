import type { TrackOutline } from '../api/client'

/** A full outline, or the light preview shipped in the event list (points only). */
export type OutlineLike = Pick<TrackOutline, 'points'> & Partial<Pick<TrackOutline, 'sector_1_end_index' | 'sector_2_end_index' | 'turns'>>
import { TIER_COLOR, type Tier } from '../lib/f1'

type Pt = [number, number]
const path = (pts: Pt[]) => pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join('')

function normal(pts: Pt[], i: number): Pt {
  const a = pts[Math.max(0, i - 2)], b = pts[Math.min(pts.length - 1, i + 2)]
  const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1
  return [-dy / len, dx / len]
}

/** Outward direction at point i: the normal pointing away from the track's centroid. */
function outward(pts: Pt[], i: number, c: Pt): Pt {
  const [nx, ny] = normal(pts, i)
  const [x, y] = pts[i]
  return (x + nx - c[0]) ** 2 + (y + ny - c[1]) ** 2 > (x - nx - c[0]) ** 2 + (y - ny - c[1]) ** 2 ? [nx, ny] : [-nx, -ny]
}

/**
 * Circuit map in F1's own orientation. Sector colouring (tiers) and turn colouring are optional:
 * the race-card thumbnails draw a plain line, the weekend page colours sectors for the selected driver.
 */
export function TrackMap({
  outline,
  sectors,
  turns,
  showTurns = false,
  stroke = 9,
  plainColor = 'var(--text-2)',
  className,
}: {
  outline: OutlineLike
  sectors?: [Tier, Tier, Tier]
  turns?: Record<number, Tier>
  showTurns?: boolean
  stroke?: number
  plainColor?: string
  className?: string
}) {
  const pts = outline.points as Pt[]
  // crop the 0-1000 box to the track so maps fill their frame regardless of aspect
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1])
  const pad = showTurns ? 60 : stroke * 2 + 6
  const minX = Math.min(...xs) - pad, maxX = Math.max(...xs) + pad, minY = Math.min(...ys) - pad, maxY = Math.max(...ys) + pad
  const c: Pt = [(minX + maxX) / 2, (minY + maxY) / 2]
  const i1 = Math.min(outline.sector_1_end_index ?? Math.floor(pts.length / 3), pts.length - 1)
  const i2 = Math.min(Math.max(outline.sector_2_end_index ?? Math.floor((2 * pts.length) / 3), i1 + 1), pts.length - 1)
  const segs: Pt[][] = [pts.slice(0, i1 + 1), pts.slice(i1, i2 + 1), [...pts.slice(i2), pts[0]]]
  const [sx, sy] = pts[0]
  const [snx, sny] = normal(pts, 0)
  const sf = stroke * 1.25

  return (
    <svg viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`} className={className} role="img" aria-label="Circuit map">
      {sectors ? (
        <>
          <path d={path([...pts, pts[0]])} fill="none" stroke="var(--bg)" strokeWidth={stroke + 6} strokeLinejoin="round" strokeLinecap="round" />
          {segs.map((seg, i) => (
            <path key={i} d={path(seg)} fill="none" stroke={TIER_COLOR[sectors[i]]} strokeWidth={stroke} strokeLinejoin="round" strokeLinecap="butt">
              <title>{`Sector ${i + 1}`}</title>
            </path>
          ))}
          {[i1, i2].map((idx) => {
            const [x, y] = pts[idx], [nx, ny] = normal(pts, idx)
            return <line key={idx} x1={x - nx * (stroke + 5)} y1={y - ny * (stroke + 5)} x2={x + nx * (stroke + 5)} y2={y + ny * (stroke + 5)} stroke="var(--bg)" strokeWidth={4} />
          })}
        </>
      ) : (
        <path d={path([...pts, pts[0]])} fill="none" stroke={plainColor} strokeWidth={stroke} strokeLinejoin="round" strokeLinecap="round" />
      )}
      {/* start / finish */}
      <line x1={sx - snx * sf} y1={sy - sny * sf} x2={sx + snx * sf} y2={sy + sny * sf} stroke="var(--text)" strokeWidth={Math.max(3, stroke / 2.5)} />
      {showTurns &&
        (outline.turns ?? []).map((t) => {
          const i = Math.min(t.index, pts.length - 1)
          const [ox, oy] = outward(pts, i, c)
          const x = pts[i][0] + ox * (stroke + 22), y = pts[i][1] + oy * (stroke + 22)
          const tier = turns?.[t.number]
          return (
            <g key={t.number}>
              {tier && tier !== 'none' && <circle cx={x} cy={y} r={14} fill={TIER_COLOR[tier]} data-turn={t.number} data-tier={tier} />}
              <text x={x} y={y + 5} textAnchor="middle" fontSize={15} fontWeight={600} fill={tier && tier !== 'none' ? '#0c0e11' : 'var(--text-3)'}>{t.number}</text>
              <title>{`Turn ${t.number}`}</title>
            </g>
          )
        })}
    </svg>
  )
}

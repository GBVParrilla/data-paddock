import type { SessionType } from '../api/client'

export const SESSION_ORDER: Record<string, number> = { FP1: 0, FP2: 1, FP3: 2, SQ: 3, S: 4, Q: 5, R: 6 }
export const SESSION_SHORT: Record<SessionType, string> = { FP1: 'FP1', FP2: 'FP2', FP3: 'FP3', SQ: 'Sprint quali', S: 'Sprint', Q: 'Qualifying', R: 'Race' }
export const SESSION_TINY: Record<SessionType, string> = { FP1: 'FP1', FP2: 'FP2', FP3: 'FP3', SQ: 'SQ', S: 'S', Q: 'Q', R: 'R' }
export const isRaceLike = (t?: string) => t === 'R' || t === 'S'
export const isQualiLike = (t?: string) => t === 'Q' || t === 'SQ'

export type Tier = 'purple' | 'green' | 'yellow' | 'red' | 'none'
export const TIER_COLOR: Record<Tier, string> = { purple: 'var(--purple)', green: 'var(--green)', yellow: 'var(--yellow)', red: 'var(--red)', none: 'var(--none)' }
export const TIER_LABEL: Record<Tier, string> = { purple: 'Fastest', green: 'Faster than average', yellow: 'Around average', red: 'Slower than average', none: 'No data' }

/** F1 timing-screen colours: purple = session best; green/yellow/red against the field's average delta. */
export function sectorTier(delta: number | null | undefined, fieldAvg: number | null): Tier {
  if (delta === null || delta === undefined) return 'none'
  if (delta <= 15) return 'purple'
  if (fieldAvg === null || fieldAvg <= 0 || delta <= fieldAvg) return 'green'
  if (delta <= fieldAvg * 1.6) return 'yellow'
  return 'red'
}

/** Turn deltas vs the reference lap use fixed thresholds (ms). */
export function turnTier(deltaMs: number | undefined): Tier {
  if (deltaMs === undefined) return 'none'
  if (deltaMs <= -30) return 'purple'
  if (deltaMs <= 60) return 'green'
  if (deltaMs <= 200) return 'yellow'
  return 'red'
}

export const TYRE: Record<string, { color: string; letter: string; label: string }> = {
  SOFT: { color: 'var(--soft)', letter: 'S', label: 'Soft' },
  MEDIUM: { color: 'var(--medium)', letter: 'M', label: 'Medium' },
  HARD: { color: 'var(--hard)', letter: 'H', label: 'Hard' },
  INTERMEDIATE: { color: 'var(--inter)', letter: 'I', label: 'Intermediate' },
  WET: { color: 'var(--wet)', letter: 'W', label: 'Wet' },
}
export const tyre = (c: string | null | undefined) => (c && TYRE[c]) || { color: 'var(--none)', letter: '?', label: 'Unknown' }

export function lastName(name: string | undefined): string {
  if (!name) return ''
  const parts = name.split(' ')
  return parts.length > 1 ? parts.slice(1).join(' ') : name
}

export function ordinal(n: number | null | undefined): string {
  return n === null || n === undefined ? '–' : `P${n}`
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso.length <= 10 ? iso + 'T00:00:00Z' : iso)
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' })
}

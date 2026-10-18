import type { HeadlineRace, RaceStatus, SessionType } from '../api/client'

export const SESSION_ORDER: Record<string, number> = { FP1: 0, FP2: 1, FP3: 2, SQ: 3, S: 4, Q: 5, R: 6 }
export const SESSION_SHORT: Record<SessionType, string> = { FP1: 'FP1', FP2: 'FP2', FP3: 'FP3', SQ: 'Sprint quali', S: 'Sprint', Q: 'Qualifying', R: 'Race' }
export const SESSION_TINY: Record<SessionType, string> = { FP1: 'FP1', FP2: 'FP2', FP3: 'FP3', SQ: 'SQ', S: 'S', Q: 'Q', R: 'R' }
export const isRaceLike = (t?: string) => t === 'R' || t === 'S'
export const isQualiLike = (t?: string) => t === 'Q' || t === 'SQ'

export type Tier = 'purple' | 'green' | 'yellow' | 'red' | 'none'
export const TIER_COLOR: Record<Tier, string> = { purple: 'var(--purple)', green: 'var(--green)', yellow: 'var(--yellow)', red: 'var(--red)', none: 'var(--none)' }
export const TIER_LABEL: Record<Tier, string> = { purple: 'Fastest of all', green: 'Top quarter', yellow: 'Middle half', red: 'Bottom quarter', none: 'No time' }

/** Sector colours from where a driver's best sector ranks among everyone who set one:
 * purple = session best (F1's convention), green = top quarter, yellow = middle half, red = bottom quarter. */
export function rankTier(rank: number | null | undefined, of: number): Tier {
  if (!rank || !of) return 'none'
  if (rank === 1) return 'purple'
  if (rank <= Math.ceil(of / 4)) return 'green'
  if (rank <= Math.ceil((of * 3) / 4)) return 'yellow'
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
// Unknown compounds (the feed didn't say) get their own hatched swatch and legend entry.
export const UNKNOWN_TYRE = { color: 'repeating-linear-gradient(135deg, var(--line-2) 0 3px, transparent 3px 6px)', letter: '?', label: 'Unknown' }
export const tyre = (c: string | null | undefined) => (c && TYRE[c]) || UNKNOWN_TYRE

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

/** 1 -> "1st", 14 -> "14th". */
export function nth(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
  return `${n}${s}`
}

export const STATUS_TEXT: Record<RaceStatus, string> = { FIN: 'Finished', LAP: 'Lapped', DNF: 'Did not finish', NC: 'Not classified', DNS: 'Did not start', DSQ: 'Disqualified' }

/** What the position column shows: the classified position, or DNF / DNS / DSQ / NC. */
export function positionLabel(r: Pick<HeadlineRace, 'finish_position' | 'status_code'>): string {
  return r.finish_position ? String(r.finish_position) : r.status_code === 'FIN' || r.status_code === 'LAP' ? '–' : r.status_code
}

/** A race gap that never mixes a time with "lapped": the time on the lead lap, "+n laps" otherwise. */
export function raceGap(r: Pick<HeadlineRace, 'finish_position' | 'status_code' | 'laps_down' | 'laps_completed'> & { gap_to_winner_ms?: number | null }): string {
  if (r.status_code === 'DNS') return ''
  if (r.status_code === 'DNF' || r.status_code === 'NC' || r.status_code === 'DSQ') return r.laps_completed ? `${r.laps_completed} laps` : ''
  if (r.finish_position === 1) return 'Winner'
  if (r.status_code === 'LAP') return `+${r.laps_down ?? 1} lap${(r.laps_down ?? 1) === 1 ? '' : 's'}`
  return r.gap_to_winner_ms != null ? `+${(r.gap_to_winner_ms / 1000).toFixed(3)}` : ''
}

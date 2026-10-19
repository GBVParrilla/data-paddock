import { useMemo } from 'react'
import type { Detail } from '../api/client'
import { rankTier, type Tier } from './f1'

export type SectorStat = { sec: 1 | 2 | 3; best: Map<number, number>; ranked: number[]; bestMs: number | null; holder: number | null }

/** Each driver's best time per sector, ranked (what every sector colour and label is computed from). */
export function useSectorStats(detail: Detail | null): SectorStat[] {
  return useMemo(() => ([1, 2, 3] as const).map((sec) => {
    const best = new Map<number, number>()
    for (const d of detail?.sector_deltas ?? []) {
      if (d.sector !== sec || d.driver_sector_ms === null) continue
      if ((best.get(d.driver_id) ?? Infinity) > d.driver_sector_ms) best.set(d.driver_id, d.driver_sector_ms)
    }
    const ranked = [...best.entries()].sort((a, b) => a[1] - b[1]).map(([id]) => id)
    return { sec, best, ranked, bestMs: ranked.length ? best.get(ranked[0])! : null, holder: ranked[0] ?? null }
  }), [detail])
}

export function sectorTiers(stats: SectorStat[], driverId: number | undefined): [Tier, Tier, Tier] | undefined {
  if (!stats.some((s) => s.ranked.length)) return undefined
  return stats.map((s) => (driverId === undefined ? 'purple' : rankTier(s.ranked.indexOf(driverId) + 1 || null, s.ranked.length))) as [Tier, Tier, Tier]
}

/** "14th, 11th and 16th of 20" style ranks for one driver, or null when they set no sector times. */
export function sectorRanks(stats: SectorStat[], driverId: number): { sec: number; rank: number; of: number }[] | null {
  const out = stats.map((s) => ({ sec: s.sec, rank: s.ranked.indexOf(driverId) + 1, of: s.ranked.length })).filter((r) => r.rank > 0)
  return out.length ? out : null
}

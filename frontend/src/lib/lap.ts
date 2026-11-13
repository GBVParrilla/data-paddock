import type { LapRow, StintRow } from '../api/client'

export type LapLine = {
  id: number; lap: number; time: number | null; pit: boolean
  /** each sector: the time, the gap to his own best in that sector, and his rank among everyone timed in it on this lap */
  sectors: ({ ms: number; toBest: number; rank: number; of: number } | null)[]
  tyre: string | null; tyreLap: number | null
}

/** One lap for some drivers, from the exported lap rows (BENCHMARKS row 21: a lap drill-down). */
export function lapLines(laps: Record<string, LapRow[]>, ids: number[], lap: number, stints: StintRow[]): LapLine[] {
  const rowOf = (id: number) => laps[String(id)]?.find((r) => r[0] === lap)
  // everyone's sector times on this lap, for the ranks
  const field = Object.keys(laps).map((k) => laps[k].find((r) => r[0] === lap)).filter(Boolean) as LapRow[]
  return ids.map((id) => {
    const r = rowOf(id)
    const mine = laps[String(id)] ?? []
    const st = stints.find((s) => s.driver_id === id && s.lap_start != null && s.lap_end != null && s.lap_start <= lap && lap <= s.lap_end)
    const sectors = [2, 3, 4].map((k) => {
      const ms = r?.[k] as number | null | undefined
      if (ms == null) return null
      const best = Math.min(...mine.map((x) => x[k] as number | null).filter((v): v is number => v != null))
      const all = field.map((x) => x[k] as number | null).filter((v): v is number => v != null)
      return { ms, toBest: ms - best, rank: all.filter((v) => v < ms).length + 1, of: all.length }
    })
    return { id, lap, time: r?.[1] ?? null, pit: r?.[5] === 1, sectors, tyre: st?.compound ?? null, tyreLap: st?.lap_start != null ? lap - st.lap_start + 1 : null }
  })
}


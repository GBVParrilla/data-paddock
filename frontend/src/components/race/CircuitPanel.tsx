import { useMemo } from 'react'
import { fmtMs, type Detail, type Driver, type Headline, type TrackOutline, type TurnDeltas } from '../../api/client'
import { nth, rankTier, TIER_COLOR, TIER_LABEL, turnTier, type Tier } from '../../lib/f1'
import { Term } from '../Glossary'
import { TrackMap } from '../TrackMap'

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

export function TierLegend({ turns }: { turns?: boolean }) {
  const tiers: Tier[] = ['purple', 'green', 'yellow', 'red']
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 label">
      <Term k="purple">Colours</Term>
      {tiers.map((t) => (
        <span key={t} className="flex items-center gap-1.5"><span className="dot" style={{ background: TIER_COLOR[t] }} />{turns ? { purple: 'Gained', green: 'Matched', yellow: 'Lost a little', red: 'Lost most', none: '' }[t] : TIER_LABEL[t]}</span>
      ))}
    </div>
  )
}

/** The circuit in its real shape, coloured by where the selected driver ranked in each sector
 * (and, when telemetry allows, through each corner). With nobody selected: the fastest sectors. */
export function CircuitPanel({ outline, outlineLoading, stats, headline, mapFor, selected, mapIdx, onMapIdx, turnDeltas }: {
  outline: TrackOutline | null; outlineLoading: boolean; stats: SectorStat[]; headline: Headline
  mapFor?: Driver; selected: Driver[]; mapIdx: number; onMapIdx: (i: number) => void; turnDeltas: TurnDeltas | null
}) {
  const tiers = sectorTiers(stats, mapFor?.id)
  const turnTiers = turnDeltas && !turnDeltas.is_reference_lap
    ? Object.fromEntries(turnDeltas.turns.map((t) => [t.number, turnTier(t.delta_ms)])) as Record<number, Tier> : undefined
  return (
    <section className="panel flex-1 flex flex-col" aria-label="Circuit">
      <div className="panel-head">
        <h2 className="h2">{mapFor ? `${mapFor.name}: sectors and corners` : 'Fastest sectors'}</h2>
        {selected.length === 2 && (
          <div className="seg sm">{selected.map((d, i) => <button key={d.id} aria-pressed={i === mapIdx} onClick={() => onMapIdx(i)}>{d.code}</button>)}</div>
        )}
      </div>
      <div className="flex-1 flex items-center justify-center px-3 sm:px-6 py-4 min-h-[220px] sm:min-h-[340px]">
        {outline ? <TrackMap outline={outline} sectors={tiers} turns={turnTiers} showTurns stroke={11} className="w-full max-h-[460px]" />
          : <span className="label">{outlineLoading ? '' : 'Circuit map unavailable'}</span>}
      </div>
      <div className="px-4 pb-3"><TierLegend /></div>
      <div className="grid grid-cols-3 border-t" style={{ borderColor: 'var(--line)' }}>
        {stats.map((s, i) => {
          const t: Tier = tiers?.[i] ?? 'none'
          const mine = mapFor ? s.best.get(mapFor.id) : undefined
          const rank = mapFor ? s.ranked.indexOf(mapFor.id) + 1 : 0
          const gap = mine !== undefined && s.bestMs !== null ? mine - s.bestMs : undefined
          return (
            <div key={s.sec} className={`px-4 py-3 min-w-0 ${i ? 'border-l' : ''}`} style={{ borderColor: 'var(--line)' }}>
              <div className="flex items-center gap-2 label"><span className="dot" style={{ background: TIER_COLOR[t] }} /><Term k="sector">Sector {s.sec}</Term></div>
              {mapFor ? (
                <>
                  <div className="text-[16px] font-semibold num mt-1">{gap === undefined ? '–' : gap === 0 ? 'Fastest' : `+${fmtMs(gap)}s`}</div>
                  <div className="text-[12px] t3 mt-0.5 truncate">{rank ? `${nth(rank)} of ${s.ranked.length} who set a time` : 'No time'}</div>
                </>
              ) : (
                <>
                  <div className="text-[16px] font-semibold num mt-1">{s.bestMs ? fmtMs(s.bestMs) : '–'}</div>
                  <div className="text-[12px] t3 mt-0.5 truncate">{s.holder ? headline.drivers[String(s.holder)]?.name : ''}</div>
                </>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

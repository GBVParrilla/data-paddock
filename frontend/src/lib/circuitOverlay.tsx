import { fmtMs, type Driver, type TurnDeltas } from '../api/client'
import { TierLegend } from '../components/race/CircuitPanel'
import { nth, TIER_COLOR, turnTier, type Tier } from './f1'
import { sectorTiers, type SectorStat } from './sectors'

/** What the race sheet's drawing shows once a driver is picked: their sector colours, their corner colours
 * (ranks across the session, REVIEW_ROUND3 #49) unless the breakdown was withheld (#48), and below it the
 * legend and each sector's gap and rank. */
export function circuitOverlay({ stats, mapFor, turnDeltas, turnsNote }: { stats: SectorStat[]; mapFor: Driver; turnDeltas: TurnDeltas | null; turnsNote?: string }) {
  const tiers = sectorTiers(stats, mapFor.id)
  const turns = turnDeltas ? Object.fromEntries(turnDeltas.turns.map((t) => [t.number, turnTier(t)])) as Record<number, Tier> : undefined
  const below = (
    <div className="mt-2">
      {turnsNote && <p className="text-[13px] t2 mb-2">{turnsNote} The map shows {mapFor.name}'s sectors only.</p>}
      <TierLegend />
      <div className="grid grid-cols-3 mt-3 border-t" style={{ borderColor: 'var(--line)' }}>
        {stats.map((s, i) => {
          const t: Tier = tiers?.[i] ?? 'none'
          const mine = s.best.get(mapFor.id)
          const rank = s.ranked.indexOf(mapFor.id) + 1
          const gap = mine !== undefined && s.bestMs !== null ? mine - s.bestMs : undefined
          return (
            <div key={s.sec} className={`pr-3 py-2 min-w-0 ${i ? 'pl-3 border-l' : ''}`} style={{ borderColor: 'var(--line)' }}>
              <div className="flex items-center gap-2 label"><span className="dot" style={{ background: TIER_COLOR[t] }} />Sector {s.sec}</div>
              <div className="text-[16px] font-semibold num mt-1">{gap === undefined ? '–' : gap === 0 ? 'Fastest' : `+${fmtMs(gap)}s`}</div>
              <div className="text-[12px] t3 mt-0.5 truncate">{rank ? `${nth(rank)} of ${s.ranked.length}` : 'No time'}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
  return { sectors: tiers, turns, below, label: `${mapFor.name}: sectors and corners` }
}

import { fmtMs, type Driver, type Headline, type TrackOutline, type TurnDeltas } from '../../api/client'
import { nth, TIER_COLOR, TIER_LABEL, turnTier, type Tier } from '../../lib/f1'
import { sectorTiers, type SectorStat } from '../../lib/sectors'
import { sectorTitle } from '../../lib/takeaways'
import { TrackMap } from '../TrackMap'

export function TierLegend({ turns }: { turns?: boolean }) {
  const tiers: Tier[] = ['purple', 'green', 'yellow', 'red']
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 label">
      {tiers.map((t) => (
        <span key={t} className="flex items-center gap-1.5"><span className="dot" style={{ background: TIER_COLOR[t] }} />{turns ? { purple: 'Gained', green: 'Matched', yellow: 'Lost a little', red: 'Lost most', none: '' }[t] : TIER_LABEL[t]}</span>
      ))}
    </div>
  )
}

/** With nobody picked: one row, a small outline and the session-best sectors. It sits on top of Key moments. */
export function SectorStrip({ outline, stats, headline }: { outline: TrackOutline | null; stats: SectorStat[]; headline: Headline }) {
  if (!stats.some((s) => s.bestMs)) return null
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b" style={{ borderColor: 'var(--line)' }} aria-label="Fastest sectors">
      <div className="w-[72px] sm:w-[96px] h-[56px] sm:h-[72px] shrink-0 flex items-center justify-center">
        {outline && <TrackMap outline={outline} sectors={sectorTiers(stats, undefined)} stroke={26} className="w-full h-full" />}
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="h2 !text-[14px]">{sectorTitle(stats, headline)}</h2>
        <dl className="grid grid-cols-3 gap-3 mt-1.5">
          {stats.map((s) => (
            <div key={s.sec} className="min-w-0">
              <dt className="label">S{s.sec}</dt>
              <dd className="text-[14px] font-semibold num">{s.bestMs ? fmtMs(s.bestMs) : '–'}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}

/** The circuit in its real shape, coloured by where the selected driver ranked in each sector
 * (and, when telemetry allows, through each corner). Shown once a driver is picked. */
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
              <div className="flex items-center gap-2 label"><span className="dot" style={{ background: TIER_COLOR[t] }} />Sector {s.sec}</div>
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

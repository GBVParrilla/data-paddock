import { TIER_COLOR, TIER_LABEL, type Tier } from '../../lib/f1'

export function TierLegend() {
  const tiers: Tier[] = ['purple', 'green', 'yellow', 'red']
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 label">
      {tiers.map((t) => (
        <span key={t} className="flex items-center gap-1.5"><span className="dot" style={{ background: TIER_COLOR[t] }} />{TIER_LABEL[t]}</span>
      ))}
    </div>
  )
}

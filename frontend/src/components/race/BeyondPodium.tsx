import type { Headline, MidfieldStory } from '../../api/client'
import { teamColor } from '../../lib/teamColors'

const STORY_TYPE: Record<string, string> = {
  big_mover: 'Big climb', close_battle: 'Close battle', points_from_deep: 'Points from deep', quali_overperformer: 'Qualifying', long_run_pace: 'Long-run pace',
}

/** Two sentences, the driver's name only where it reads naturally. */
function trim(name: string, text: string): string {
  return text.split(/(?<=\.)\s+/).slice(0, 2)
    .map((t) => t.replace(new RegExp(`^(${name}|He) `), ''))
    .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
    .join(' ')
}

/** Midfield and underdog storylines, given the same billing as the podium: the way into a driver's weekend. */
export function BeyondPodium({ spot, drivers, onPick }: { spot: MidfieldStory; drivers: Headline['drivers']; onPick: (id: number) => void }) {
  const cards = [
    { id: spot.driver_id, name: spot.driver, reason: spot.reason, types: spot.story_types },
    ...spot.runners_up.slice(0, 3).map((r) => ({ id: r.driver_id, name: r.driver, reason: r.reason, types: r.story_types ?? [] })),
  ]
  return (
    <section className="panel" aria-label="Beyond the podium">
      <div className="panel-head"><h2 className="h2">Beyond the podium</h2><span className="label">Pick a driver to follow their weekend</span></div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4">
        {cards.map((c, i) => {
          const d = drivers[String(c.id)]
          const tag = STORY_TYPE[c.types.find((t) => STORY_TYPE[t]) ?? ''] ?? 'Midfield story'
          return (
            <button key={c.id} onClick={() => onPick(c.id)} className="lift relative overflow-hidden rounded-lg border text-left p-4 pt-5 flex flex-col" style={{ borderColor: 'var(--line)', background: i === 0 ? 'var(--panel-2)' : 'transparent' }}>
              <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: teamColor(d?.team) }} />
              <div className="kicker">{tag}</div>
              <div className="display font-bold text-[19px] mt-2 leading-tight">{c.name}</div>
              <div className="label mt-0.5">{d?.team}</div>
              <p className="text-[13px] t2 mt-3 flex-1">{trim(c.name, c.reason)}</p>
              <div className="text-[12.5px] font-medium mt-4">Read their weekend <span aria-hidden="true">→</span></div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

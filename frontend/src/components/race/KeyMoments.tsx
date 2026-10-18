import type { Headline, PivotalMoment } from '../../api/client'
import { teamColor } from '../../lib/teamColors'
import { Term } from '../Glossary'

const LABEL: Record<string, { text: string; term?: string }> = {
  dns: { text: 'Did not start', term: 'DNS' }, dnf: { text: 'Retirement', term: 'DNF' }, recovery: { text: 'Recovery' }, drop: { text: 'Lost places' },
  grid: { text: 'Grid drop', term: 'grid' }, safety_car: { text: 'Safety car', term: 'SC' }, vsc: { text: 'VSC', term: 'VSC' }, red_flag: { text: 'Red flag', term: 'red' },
  penalty: { text: 'Penalty' }, lead_change: { text: 'Lead change' }, undercut: { text: 'Undercut', term: 'undercut' }, overcut: { text: 'Overcut', term: 'overcut' },
  slow_stop: { text: 'Slow stop' }, pit_cycle: { text: 'Pit stops' }, incident: { text: 'Stewards' }, fastest_lap: { text: 'Fastest lap' },
  pole: { text: 'Pole', term: 'pole' }, knocked_out: { text: 'Knocked out', term: 'Q' }, no_time: { text: 'No time' }, cut_line: { text: 'Close call', term: 'Q' },
  midfield_q3: { text: 'Midfield' }, fastest: { text: 'Pace setter' }, midfield_pace: { text: 'Midfield' },
}

function lapLabel(m: PivotalMoment): string {
  if (m.lap_number === 0) return 'Start'
  if (m.lap_number == null) return ''
  return m.end_lap && m.end_lap !== m.lap_number ? `L${m.lap_number}–${m.end_lap}` : `L${m.lap_number}`
}

/** What decided the session, in lap order. Clicking a moment opens that driver's story. */
export function KeyMoments({ moments, drivers, onPick, raceLike }: { moments: PivotalMoment[]; drivers: Headline['drivers']; onPick: (id: number) => void; raceLike: boolean }) {
  if (!moments.length) return null
  const ordered = [...moments].sort((a, b) => (a.lap_number ?? 9999) - (b.lap_number ?? 9999) || b.magnitude_score - a.magnitude_score)
  return (
    <section className="panel" aria-label="Key moments">
      <div className="panel-head"><h2 className="h2">Key moments</h2><span className="label">{raceLike ? 'What decided the race, in lap order' : 'What stood out'}</span></div>
      <ol className="px-4 pb-3 pt-2">
        {ordered.map((m) => {
          const d = m.driver_id !== null ? drivers[String(m.driver_id)] : undefined
          const kind = LABEL[m.moment_type] ?? { text: m.moment_type.replace(/_/g, ' ') }
          const body = (
            <>
              <span className="num t3 text-[12px] w-12 shrink-0 pt-[3px]">{lapLabel(m)}</span>
              <span className="swatch h-4 mt-[3px] shrink-0" style={{ background: d ? teamColor(d.team) : 'var(--yellow)' }} />
              <span className="min-w-0">
                <span className="label mr-2">{kind.term ? <Term k={kind.term}>{kind.text}</Term> : kind.text}</span>
                <span className="text-[13.5px]">{m.headline ?? m.description}</span>
                {m.detail && <span className="block text-[12.5px] t2 mt-0.5">{m.detail}</span>}
              </span>
            </>
          )
          return (
            <li key={m.id} className="border-t first:border-t-0" style={{ borderColor: 'var(--line)' }}>
              {d
                ? <div role="button" tabIndex={0} onClick={() => onPick(d.id)} onKeyDown={(e) => { if (e.key === 'Enter') onPick(d.id) }}
                    className="w-full flex items-start gap-3 py-2.5 text-left hover:bg-[var(--hover)] rounded-md px-1 cursor-pointer">{body}</div>
                : <div className="flex items-start gap-3 py-2.5 px-1">{body}</div>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

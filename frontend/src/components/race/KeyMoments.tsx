import type { ReactNode } from 'react'
import type { Headline, PivotalMoment } from '../../api/client'
import { factOf, type MidfieldItem } from '../../lib/mentions'
import { teamColor } from '../../lib/teamColors'
import { Term } from '../Glossary'

const LABEL: Record<string, { text: string; term?: string }> = {
  dns: { text: 'Did not start' }, dnf: { text: 'Retirement' }, recovery: { text: 'Recovery' }, drop: { text: 'Lost places' },
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

/** What decided the session, in lap order, then up to two midfield drivers nobody has mentioned yet.
 * Facts the 30-second summary already gave are left out (lib/mentions). Clicking a row opens that driver. */
export function KeyMoments({ moments, midfield, drivers, onPick, top }: {
  moments: PivotalMoment[]; midfield: MidfieldItem[]; drivers: Headline['drivers']; onPick: (id: number) => void; top?: ReactNode
}) {
  if (!moments.length && !midfield.length && !top) return null
  const ordered = [...moments].sort((a, b) => (a.lap_number ?? 9999) - (b.lap_number ?? 9999) || b.magnitude_score - a.magnitude_score)
  const rows: { key: string; driverId: number | null; lap: string; kind: ReactNode; text: string; detail?: string | null; fact: string }[] = [
    ...ordered.map((m) => {
      const kind = LABEL[m.moment_type] ?? { text: m.moment_type.replace(/_/g, ' ') }
      return { key: `m${m.id}`, driverId: m.driver_id, lap: lapLabel(m), kind: kind.term ? <Term k={kind.term}>{kind.text}</Term> : kind.text, text: m.headline ?? m.description, detail: m.detail, fact: factOf(m) }
    }),
    ...midfield.map((x) => ({ key: `f${x.driver_id}`, driverId: x.driver_id, lap: '', kind: 'Midfield', text: x.text, fact: x.fact })),
  ]
  return (
    <section className="panel" aria-label="Key moments">
      {top}
      {rows.length > 0 && <>
        <div className="panel-head"><h2 className="h2">Key moments</h2></div>
        <ol className="px-4 pb-3 pt-2">
          {rows.map((r) => {
            const d = r.driverId !== null ? drivers[String(r.driverId)] : undefined
            const body = (
              <>
                <span className="num t3 text-[12px] w-12 shrink-0 pt-[3px]">{r.lap}</span>
                <span className="swatch h-4 mt-[3px] shrink-0" style={{ background: d ? teamColor(d.team) : 'var(--yellow)' }} />
                <span className="min-w-0">
                  <span className="label mr-2">{r.kind}</span>
                  <span className="text-[13.5px]">{r.text}</span>
                  {r.detail && <span className="block text-[12.5px] t2 mt-0.5">{r.detail}</span>}
                </span>
              </>
            )
            return (
              <li key={r.key} className="border-t first:border-t-0" style={{ borderColor: 'var(--line)' }} data-fact={r.fact}>
                {d
                  ? <div role="button" tabIndex={0} onClick={() => onPick(d.id)} onKeyDown={(e) => { if (e.key === 'Enter') onPick(d.id) }}
                      className="w-full flex items-start gap-3 py-2.5 text-left hover:bg-[var(--hover)] rounded-md px-1 cursor-pointer">{body}</div>
                  : <div className="flex items-start gap-3 py-2.5 px-1">{body}</div>}
              </li>
            )
          })}
        </ol>
      </>}
    </section>
  )
}

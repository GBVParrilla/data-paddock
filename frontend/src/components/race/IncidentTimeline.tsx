import { api, type Headline } from '../../api/client'
import { useFetch } from '../../hooks/useFetch'
import { teamColor } from '../../lib/teamColors'
import { Term } from '../Glossary'

const KIND: Record<string, { label: string; term?: string }> = {
  neutralisation: { label: 'Neutralised', term: 'VSC' }, red_flag: { label: 'Red flag', term: 'red' }, penalty: { label: 'Penalty' },
  investigation: { label: 'Investigation' }, decision: { label: 'Decision' }, track_limits: { label: 'Track limits', term: 'tracklimits' },
  warning: { label: 'Warning' }, info: { label: 'Notice' },
}

/** Everything race control said that a fan would want to know, in order. Stewards' cases are grouped
 * into one line each (noted, investigated, decided), the same fact both drivers' stories use. */
export function IncidentTimeline({ sessionId, headline, selected }: { sessionId: number; headline: Headline; selected: number[] }) {
  const rc = useFetch((s) => api.raceControl(sessionId, s), [sessionId])
  if (rc.loading) return <div className="skeleton h-40" />
  if (rc.error || !rc.data) return <p className="t2">No race-control messages for this session.</p>
  const code = (id: number) => headline.drivers[String(id)]?.code ?? `#${id}`
  const team = (id: number) => headline.drivers[String(id)]?.team
  const events = rc.data.events.filter((e) => !['investigation', 'decision'].includes(e.kind) && (!selected.length || !e.driver_ids.length || e.driver_ids.some((d) => selected.includes(d))))
  const cases = rc.data.cases.filter((c) => !selected.length || c.driver_ids.some((d) => selected.includes(d)))
  const rows = [
    ...events.map((e) => ({ lap: e.lap_number, kind: e.kind, ids: e.driver_ids, text: e.text })),
    ...cases.map((c) => ({
      lap: c.opened_lap, kind: c.outcome && c.outcome !== 'no further action' ? 'penalty' : 'investigation', ids: c.driver_ids,
      text: `${c.driver_ids.map(code).join(' and ')}${c.turn ? `, turn ${c.turn}` : ''}${c.reason ? ` (${c.reason})` : ''}: ${c.outcome ?? (c.after_race ? 'investigated after the race' : 'noted')}${c.decided_lap && c.decided_lap !== c.opened_lap ? `, decided on lap ${c.decided_lap}` : ''}.`,
    })),
  ].sort((a, b) => (a.lap ?? 0) - (b.lap ?? 0))
  if (!rows.length) return <p className="t2">Nothing from race control{selected.length ? ' involving the selected drivers' : ''} in this session.</p>
  return (
    <div>
      <p className="label mb-3">{selected.length ? 'Messages involving the selected drivers, plus neutralisations.' : 'Neutralisations, penalties, stewards\' cases and deleted laps.'} Stewards' cases are shown once, with their outcome.</p>
      <ol className="divide-y" style={{ borderColor: 'var(--line)' }}>
        {rows.map((r, i) => {
          const k = KIND[r.kind] ?? KIND.info
          return (
            <li key={i} className="grid grid-cols-[3rem_7.5rem_1fr] gap-3 py-2 items-start text-[13px]" style={{ borderColor: 'var(--line)' }}>
              <span className="num t3">{r.lap ? `L${r.lap}` : ''}</span>
              <span className="label">{k.term ? <Term k={k.term}>{k.label}</Term> : k.label}</span>
              <span className="flex items-start gap-2 min-w-0">
                {r.ids.slice(0, 2).map((id) => <span key={id} className="swatch h-4 mt-[2px] shrink-0" style={{ background: teamColor(team(id)) }} />)}
                <span className="t2">{r.text}</span>
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

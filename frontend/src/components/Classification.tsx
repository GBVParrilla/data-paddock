import type { Driver, Headline, HeadlineRace } from '../api/client'
import { fmtMs } from '../api/client'
import { positionLabel, raceGap, STATUS_TEXT } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { Term } from './Glossary'

type Row = { id: number; pos: string; out?: boolean; note?: string; cells: (string | React.ReactNode)[] }

function Delta({ v }: { v: number | null | undefined }) {
  if (!v) return <span className="t3">–</span>
  const up = v > 0
  return (
    <span className="inline-flex items-center gap-1 num" aria-label={`${up ? 'gained' : 'lost'} ${Math.abs(v)}`}>
      <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true"><path d={up ? 'M4 1 7 6H1z' : 'M4 7 1 2h6z'} fill={up ? 'var(--green)' : 'var(--red)'} /></svg>
      {Math.abs(v)}
    </span>
  )
}

const OUT_TERM: Record<string, string> = { DNF: 'DNF', DNS: 'DNS', DSQ: 'DSQ', NC: 'NC' }

function raceRows(rows: (HeadlineRace & { gap_to_winner_ms?: number | null })[]): Row[] {
  // server order is the official classification: classified cars, then unclassified, DNS, DSQ
  return rows.map((r) => {
    const out = !r.finish_position && r.status_code !== 'FIN' && r.status_code !== 'LAP'
    const classifiedRetirement = r.finish_position && (r.status_code === 'DNF' || r.status_code === 'NC')
    return {
      id: r.driver_id,
      pos: positionLabel(r),
      out,
      note: classifiedRetirement ? 'Retired, classified' : undefined,
      cells: [raceGap(r), r.grid_position ?? (r.status_code === 'DNS' ? '–' : 'Pit'), <Delta key="d" v={r.positions_gained} />, r.status_code === 'DNS' ? '' : r.pit_stop_count, r.points || ''],
    }
  })
}

/** Session results. Clicking a row selects that driver (a second click on another adds a comparison). */
export function Classification({ headline, selected, colors, onSelect }: { headline: Headline; selected: number[]; colors: string[]; onSelect: (id: number) => void }) {
  const drv = (id: number): Driver | undefined => headline.drivers[String(id)]
  const sq = headline.session.session_type === 'SQ'
  let head: React.ReactNode[] = []
  let rows: Row[] = []
  // columns hidden on phones: Grid and Stops (+/− already shows the grid move); Pts stays (REVIEW_ROUND2 #45)
  let phoneHidden = new Set<number>()
  if (headline.practice) {
    head = ['Best lap', 'Gap']
    rows = [...headline.practice].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
      .map((r) => ({ id: r.driver_id, pos: r.rank ? String(r.rank) : '–', cells: [fmtMs(r.fastest_lap_ms), r.gap_to_fastest_ms ? `+${fmtMs(r.gap_to_fastest_ms)}` : ''] }))
  } else if (headline.qualifying) {
    head = [<span key="g">Gap <span className="t3 font-normal">(in segment)</span></span>, 'Out']
    rows = [...headline.qualifying].sort((a, b) => (a.position ?? 99) - (b.position ?? 99)).map((r) => {
      const seg = r.gap_segment ? (sq ? `S${r.gap_segment}` : r.gap_segment) : ''
      const gap = r.status_code === 'NO_TIME' ? 'No time'
        : r.position === 1 ? 'Pole'
        : r.gap_to_pole_ms != null ? <span key="g">+{fmtMs(r.gap_to_pole_ms)} <span className="t3 text-[11px]">{seg}</span></span>
        : <span key="g" className="t3">No {sq ? 'SQ3' : 'Q3'} time</span>
      const out = r.eliminated_in ? (sq ? `S${r.eliminated_in}` : r.eliminated_in) : ''
      return { id: r.driver_id, pos: r.position ? String(r.position) : '–', out: r.status_code === 'NO_TIME', cells: [gap, out] }
    })
  } else if (headline.race) {
    head = ['Gap', 'Grid', '+/−', 'Stops', 'Pts']
    rows = raceRows(headline.race)
    phoneHidden = new Set([1, 3])
  }
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th className="w-10">Pos</th>
          <th>Driver</th>
          {head.map((h, i) => <th key={i} className={`r ${phoneHidden.has(i) ? 'hidden sm:table-cell' : ''}`}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const d = drv(r.id)
          const sel = selected.indexOf(r.id)
          const status = headline.race?.find((x) => x.driver_id === r.id)?.status_code
          return (
            <tr key={r.id} className="clickable" aria-selected={sel !== -1} onClick={() => onSelect(r.id)} tabIndex={0} data-driver={r.id} data-pos={r.pos}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(r.id) } }}>
              <td className="num t2">
                {r.out && OUT_TERM[r.pos] ? <span className="text-[11px] font-semibold t3"><Term k={r.pos}>{r.pos}</Term></span> : r.pos}
              </td>
              <td>
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="swatch h-4" style={{ background: sel !== -1 ? colors[sel] : teamColor(d?.team), opacity: sel !== -1 ? 1 : 0.85 }} />
                  <span className="font-semibold w-9 shrink-0">{d?.code ?? ''}</span>
                  <span className="t2 truncate max-w-[9rem] hidden sm:inline lg:hidden">{d?.name}</span>
                  {d?.stand_in && <span className="chip shrink-0" title={`Usually drives for ${d.usual_team}`}>Stand-in</span>}
                  {r.note && <span className="label shrink-0 hidden xl:inline" title={status ? STATUS_TEXT[status] : undefined}>{r.note}</span>}
                </div>
              </td>
              {r.cells.map((c, i) => <td key={i} className={`r num t2 ${phoneHidden.has(i) ? 'hidden sm:table-cell' : ''}`}>{c}</td>)}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

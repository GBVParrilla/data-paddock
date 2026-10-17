import type { Driver, Headline } from '../api/client'
import { fmtMs } from '../api/client'
import { teamColor } from '../lib/teamColors'

type Row = { id: number; pos: number | null; status?: string | null; cells: (string | React.ReactNode)[] }

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

/** Session results. Clicking a row selects that driver (a second click on another adds a comparison). */
export function Classification({ headline, selected, colors, onSelect }: { headline: Headline; selected: number[]; colors: string[]; onSelect: (id: number) => void }) {
  const drv = (id: number): Driver | undefined => headline.drivers[String(id)]
  let head: string[] = []
  let rows: Row[] = []
  if (headline.practice) {
    head = ['Best lap', 'Gap']
    rows = headline.practice.map((r) => ({ id: r.driver_id, pos: r.rank, cells: [fmtMs(r.fastest_lap_ms), r.gap_to_fastest_ms ? `+${fmtMs(r.gap_to_fastest_ms)}` : ''] }))
  } else if (headline.qualifying) {
    head = ['Gap', 'Out']
    rows = headline.qualifying.map((r) => ({ id: r.driver_id, pos: r.position, cells: [r.gap_to_pole_ms ? `+${fmtMs(r.gap_to_pole_ms)}` : r.position === 1 ? 'Pole' : '', r.eliminated_in ?? ''] }))
  } else if (headline.race) {
    head = ['Grid', '+/−', 'Stops', 'Pts']
    rows = headline.race.map((r) => {
      const out = r.status && !/^(Finished|Lapped|\+\d+ Laps?)$/i.test(r.status)
      return { id: r.driver_id, pos: r.finish_position, status: out ? r.status : null, cells: [r.grid_position ?? '–', <Delta key="d" v={r.positions_gained} />, r.pit_stop_count, r.points || ''] }
    })
  }
  rows.sort((a, b) => (a.pos ?? 99) - (b.pos ?? 99))
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th className="w-10">Pos</th>
          <th>Driver</th>
          {head.map((h) => <th key={h} className="r">{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const d = drv(r.id)
          const sel = selected.indexOf(r.id)
          return (
            <tr key={r.id} className="clickable" aria-selected={sel !== -1} onClick={() => onSelect(r.id)} tabIndex={0} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(r.id))}>
              <td className="num t2">{r.status ? <span className="t3 text-[11px]">{r.status.length > 4 ? 'DNF' : r.status}</span> : (r.pos ?? '–')}</td>
              <td>
                <div className="flex items-center gap-2.5">
                  <span className="swatch h-4" style={{ background: sel !== -1 ? colors[sel] : teamColor(d?.team), opacity: sel !== -1 ? 1 : 0.85 }} />
                  <span className="font-semibold w-9">{d?.code ?? ''}</span>
                  <span className="t2 truncate max-w-[9rem] hidden sm:inline">{d?.name}</span>
                </div>
              </td>
              {r.cells.map((c, i) => <td key={i} className="r num t2">{c}</td>)}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

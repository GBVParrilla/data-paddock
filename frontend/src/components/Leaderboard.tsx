import type { Driver, Headline } from '../api/client'
import { fmtMs } from '../api/client'
import { teamColor } from '../lib/teamColors'

export function Leaderboard({
  headline,
  selected,
  highlightColors,
  spotlightId,
  onSelect,
}: {
  headline: Headline
  selected: number[]
  highlightColors: string[]
  spotlightId?: number | null
  onSelect: (id: number) => void
}) {
  const d = (id: number): Driver | undefined => headline.drivers[String(id)]
  type Row = { id: number; pos: number | null; main: string; sub: string }
  let rows: Row[] = []
  let cols: [string, string] = ['', '']
  if (headline.practice) {
    cols = ['Fastest lap', 'Gap']
    rows = headline.practice.map((r) => ({ id: r.driver_id, pos: r.rank, main: fmtMs(r.fastest_lap_ms), sub: r.gap_to_fastest_ms ? fmtMs(r.gap_to_fastest_ms, true) : '' }))
  } else if (headline.qualifying) {
    cols = ['Gap to pole', 'Out in']
    rows = headline.qualifying.map((r) => ({ id: r.driver_id, pos: r.position, main: r.gap_to_pole_ms ? fmtMs(r.gap_to_pole_ms, true) : 'pole', sub: r.eliminated_in ?? 'Q3' }))
  } else if (headline.race) {
    cols = ['Grid → Finish', 'Pts / stops']
    rows = headline.race.map((r) => ({
      id: r.driver_id,
      pos: r.finish_position,
      main: `P${r.grid_position ?? '?'} → P${r.finish_position ?? '?'}${r.positions_gained ? ` (${r.positions_gained > 0 ? '+' : ''}${r.positions_gained})` : ''}`,
      sub: r.status && r.status !== 'Finished' && r.status !== 'Lapped' ? r.status : `${r.points} pts · ${r.pit_stop_count} stop${r.pit_stop_count === 1 ? '' : 's'}`,
    }))
  }
  rows.sort((a, b) => (a.pos ?? 99) - (b.pos ?? 99))
  return (
    <div className="card overflow-hidden">
      <div className="grid grid-cols-[2.2rem_1fr_6.5rem_5.5rem] gap-2 px-3 py-2 text-[11px] uppercase tracking-wide faint border-b" style={{ borderColor: 'var(--line)' }}>
        <span>Pos</span><span>Driver</span><span>{cols[0]}</span><span>{cols[1]}</span>
      </div>
      <ul className="max-h-[520px] overflow-auto">
        {rows.map((r) => {
          const drv = d(r.id)
          const hi = selected.indexOf(r.id)
          const bar = hi !== -1 ? highlightColors[hi] : teamColor(drv?.team)
          return (
            <li key={r.id}>
              <button
                onClick={() => onSelect(r.id)}
                aria-pressed={hi !== -1}
                className="w-full grid grid-cols-[2.2rem_1fr_6.5rem_5.5rem] gap-2 px-3 py-1.5 text-sm text-left hover:bg-[var(--surface-1)]"
                style={{ boxShadow: `inset 4px 0 0 ${bar}`, background: hi !== -1 ? 'var(--surface-1)' : undefined }}
              >
                <span className="font-mono muted">{r.pos ?? '–'}</span>
                <span className="truncate">
                  <span className="font-semibold">{drv?.code ?? drv?.name ?? r.id}</span> <span className="muted">{drv?.name}</span>
                  {spotlightId === r.id && <span className="ml-1 text-[10px] px-1 rounded align-middle font-bold" style={{ background: 'var(--accent)', color: 'white' }}>SPOTLIGHT</span>}
                  <span className="faint text-xs"> · {drv?.team}</span>
                </span>
                <span className="font-mono text-xs self-center">{r.main}</span>
                <span className="text-xs self-center muted truncate">{r.sub}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

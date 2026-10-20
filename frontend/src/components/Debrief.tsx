import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Debrief as DebriefData } from '../api/client'
import { nth, tyre } from '../lib/f1'

const DASH = '—'
const show = (v: ReactNode | null | undefined) => (v === null || v === undefined || v === '' ? DASH : v)

/** A small table. A value the data doesn't have is a dash; the one note says why, under the table (visible on
 * phones too, not a hover). */
function Table({ caption, head, rows, note }: { caption: string; head: string[]; rows: ReactNode[][]; note?: string }) {
  return (
    <div className="min-w-0">
      <h4 className="label mb-1.5">{caption}</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px] num" title={note}>
          <thead>
            <tr className="label text-left">{head.map((h, i) => <th key={h} scope="col" className={`font-medium pb-1 pr-3 ${i ? 'text-right' : ''}`}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t" style={{ borderColor: 'var(--line)' }}>
                {r.map((c, j) => <td key={j} className={`py-1 pr-3 ${j ? 'text-right' : ''} ${j < r.length - 1 ? 'whitespace-nowrap' : ''}`}>{show(c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {note && <p className="text-[12px] t3 mt-1">{note}</p>}
    </div>
  )
}

const tyreName = (t: string | null) => (t ? tyre(t).label : null)
const signed = (n: number | null) => (n === null ? null : n > 0 ? `+${n}` : String(n))

/** The Expert view of a driver's session: three numbered findings, then the tables an engineer would look at.
 * Everything here is computed from the timing data (no prose to get wrong); /methods explains each figure. */
export function Debrief({ d }: { d: DebriefData }) {
  const sectors = d.sectors?.length ? (
    <Table caption="Sectors (his best, against the session best)" head={['Sector', 'Best', 'Gap', 'Rank']}
      rows={d.sectors.map((s) => [`S${s.sector}`, s.best, s.gap, s.rank && s.of ? `${nth(s.rank)} of ${s.of}` : null])} />
  ) : null
  return (
    <div data-debrief={d.kind}>
      {d.findings.length > 0 && (
        <ol className="space-y-1.5 mt-3" aria-label="Findings">
          {d.findings.map((f) => (
            <li key={f.n} className="flex gap-3 text-[14.5px]">
              <span className="num font-semibold t3 w-4 shrink-0">{f.n}</span><span>{f.text}</span>
            </li>
          ))}
        </ol>
      )}
      <div className="grid md:grid-cols-2 gap-x-8 gap-y-5 mt-5">
        {d.kind === 'race' && (
          <>
            <div className="md:col-span-2">
              <Table caption="Stints" head={['Tyre', 'Laps', 'Pace (fuel-corrected)', 'Fade per lap', 'vs teammate, same tyre']} note={d.notes.stints}
                rows={(d.stints ?? []).map((s) => [tyreName(s.tyre), s.laps, s.avg_pace, s.degradation_s_per_lap === null ? null : `${s.degradation_s_per_lap > 0 ? '+' : ''}${s.degradation_s_per_lap.toFixed(3)}s`, s.vs_teammate_same_tyre])} />
            </div>
            {(d.stops?.length ?? 0) > 0 && (
              <div className="md:col-span-2">
                <Table caption="Pit stops" head={['Lap', 'Pit lane', 'Stationary', 'Places', 'Timing']} note={d.notes.stops}
                  rows={d.stops!.map((s) => [s.lap, s.pit_lane, s.stationary, s.positions ? `${s.positions} (${signed(s.net_places) ?? '0'})` : null, s.timing])} />
              </div>
            )}
            {sectors}
          </>
        )}
        {d.kind === 'qualifying' && (
          <>
            <Table caption="Segments" head={['Segment', 'Best', 'To the cut line', 'vs teammate']} note={d.notes.segments}
              rows={(d.segments ?? []).map((s) => [s.segment, s.best, s.cut_margin, s.vs_teammate])} />
            {sectors}
            {d.runs?.length ? <Table caption="Tyre runs" head={['Tyre', 'Laps', 'Best']} rows={d.runs.map((r) => [tyreName(r.tyre), r.laps, r.best])} /> : null}
          </>
        )}
        {d.kind === 'practice' && (
          <>
            <Table caption="One lap" head={['Rank', 'Best', 'Gap']}
              rows={[[d.single_lap?.rank && d.single_lap.of ? `${nth(d.single_lap.rank)} of ${d.single_lap.of}` : null, d.single_lap?.best, d.single_lap?.gap]]} />
            {d.long_runs?.length ? (
              <Table caption="Long runs" head={['Tyre', 'Average', 'Laps', 'Rank']} note={d.notes.long_runs}
                rows={d.long_runs.map((x) => [tyreName(x.tyre), x.avg, x.laps, x.rank && x.of ? `${nth(x.rank)} of ${x.of}` : null])} />
            ) : null}
            {d.run_plan?.length ? <Table caption="Run plan" head={['Tyre', 'Laps', 'Average']} rows={d.run_plan.map((r) => [tyreName(r.tyre), `${r.laps} (${r.lap_count})`, r.avg])} /> : null}
            {sectors}
            <p className="text-[12px] t3 md:col-span-2" data-practice-caveat>Practice pace is a guide: fuel loads and engine modes aren't published.</p>
          </>
        )}
      </div>
      <p className="text-[12px] t3 mt-4"><Link to="/methods" className="underline underline-offset-2 hover:text-[var(--text)]">How these numbers are computed</Link></p>
    </div>
  )
}

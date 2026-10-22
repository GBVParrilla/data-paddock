import type { Driver } from '../api/client'
import { fmtMs } from '../api/client'
import { nth, tyre } from '../lib/f1'
import type { LapLine } from '../lib/lap'

const toBest = (ms: number) => (ms <= 0 ? 'Best' : `+${fmtMs(ms)}s`)

/**
 * One lap, picked on a chart (or with the lap picker): each driver's lap time and three sectors, each sector
 * against his own best and ranked among everyone on that lap, the tyre and how old it was, and whether it was a
 * pit lap. When this is the lap the corner map was drawn from, it says so.
 */
export function LapCard({ lap, lines, drivers, colors, laps, cornerLap, onLap }: {
  lap: number; lines: LapLine[]; drivers: Record<string, Driver>; colors: string[]; laps: number[]; cornerLap?: number | null; onLap: (lap: number | null) => void
}) {
  const i = laps.indexOf(lap)
  return (
    <section className="border-t mt-3 pt-3" style={{ borderColor: 'var(--line)' }} aria-label={`Lap ${lap}`} data-lap-card={lap}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="h2">Lap {lap}</h3>
        <div className="flex items-center gap-1">
          <button type="button" className="btn-ghost text-[16px] px-2" disabled={i <= 0} onClick={() => onLap(laps[i - 1])} aria-label="Previous lap">‹</button>
          <button type="button" className="btn-ghost text-[16px] px-2" disabled={i === -1 || i >= laps.length - 1} onClick={() => onLap(laps[i + 1])} aria-label="Next lap">›</button>
          <button type="button" className="btn-ghost text-[12px]" onClick={() => onLap(null)}>Close</button>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-x-8 gap-y-4 mt-2">
        {lines.map((l, k) => {
          const d = drivers[String(l.id)]
          return (
            <div key={l.id} className="min-w-0" data-lap-driver={l.id}>
              <div className="flex items-baseline gap-2">
                <span className="swatch h-3.5 w-1 shrink-0" style={{ background: colors[k] }} />
                <span className="font-semibold">{d?.name ?? l.id}</span>
                <span className="num ml-auto text-[15px] font-semibold">{l.time ? fmtMs(l.time) : '–'}</span>
              </div>
              <p className="text-[12.5px] t2 mt-0.5">
                {[l.tyre ? `${tyre(l.tyre).label}${l.tyreLap ? `, lap ${l.tyreLap} of the stint` : ''}` : null, l.pit ? 'pit lap (in or out)' : null, cornerLap === l.lap && k === 0 ? 'the lap the corner map shows' : null].filter(Boolean).join('; ') || ' '}
              </p>
              <table className="w-full text-[13px] num mt-1.5">
                <thead>
                  <tr className="label text-right">
                    <th scope="col" className="font-medium text-left pb-1"><span className="sr-only">Sector</span></th>
                    <th scope="col" className="font-medium pb-1 pr-3">Time</th>
                    <th scope="col" className="font-medium pb-1 pr-3">To his best</th>
                    <th scope="col" className="font-medium pb-1">This lap</th>
                  </tr>
                </thead>
                <tbody>
                  {l.sectors.map((s, j) => (
                    <tr key={j} className="border-t" style={{ borderColor: 'var(--line)' }}>
                      <th scope="row" className="font-medium text-left py-1 pr-3 t2">S{j + 1}</th>
                      <td className="py-1 pr-3 text-right">{s ? fmtMs(s.ms) : '–'}</td>
                      <td className="py-1 pr-3 text-right t2 whitespace-nowrap">{s ? toBest(s.toBest) : ''}</td>
                      <td className="py-1 text-right t2 whitespace-nowrap">{s && s.of >= 3 ? `${nth(s.rank)} of ${s.of}` : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        })}
      </div>
    </section>
  )
}

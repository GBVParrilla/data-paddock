import type { ReactNode } from 'react'
import { fmtMs, type Headline, type PivotalMoment, type SessionType } from '../../api/client'
import { isQualiLike, isRaceLike } from '../../lib/f1'
import type { Line } from '../../lib/mentions'
import { teamColor } from '../../lib/teamColors'
import { Term } from '../Glossary'

type Chip = { label: ReactNode; value: string; color?: string }

const NEUTRAL = new Set(['safety_car', 'vsc', 'red_flag'])

/** "The race in 30 seconds": three plain sentences (planned in lib/mentions so no fact repeats further down)
 * and three numbers, built from the computed data - nothing here is AI-written. */
export function SessionSummary({ headline, moments, sentences, sessionType }: { headline: Headline; moments: PivotalMoment[]; sentences: Line[]; sessionType: SessionType }) {
  const d = (id?: number | null) => (id != null ? headline.drivers[String(id)] : undefined)
  const chips: Chip[] = []
  if (isRaceLike(sessionType) && headline.race) {
    const laps = Math.max(0, ...headline.race.map((r) => r.laps_completed ?? 0))
    chips.push({ label: 'Laps', value: String(laps) })
    const c = headline.counts
    if (c) chips.push({ label: <><Term k="DNF">DNF</Term> · <Term k="DNS">DNS</Term></>, value: `${c.dnf} · ${c.dns}` })
    const neutral = moments.filter((m) => NEUTRAL.has(m.moment_type))
    // "1 Red · 2 VSC", not one label per period
    const label = (['red_flag', 'safety_car', 'vsc'] as const)
      .map((t) => [neutral.filter((m) => m.moment_type === t).length, t === 'vsc' ? 'VSC' : t === 'safety_car' ? 'SC' : 'Red'] as const)
      .filter(([n]) => n).map(([n, l]) => `${n} ${l}`).join(' · ')
    chips.push({ label: <><Term k="SC">Safety car</Term> periods</>, value: neutral.length ? label : '0' })
  } else if (isQualiLike(sessionType) && headline.qualifying) {
    const q = headline.qualifying.filter((r) => r.position).sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
    const pole = q[0]
    const sq = sessionType === 'SQ'
    if (pole?.q3_ms) chips.push({ label: 'Pole lap', value: fmtMs(pole.q3_ms), color: teamColor(d(pole.driver_id)?.team) })
    const p10 = q[9]
    if (p10?.gap_segment === 'Q3' && p10.gap_to_pole_ms != null) chips.push({ label: 'Pole to P10', value: `${fmtMs(p10.gap_to_pole_ms)}s` })
    const noTime = headline.qualifying.filter((r) => r.status_code === 'NO_TIME').length
    if (noTime) chips.push({ label: 'Set no time', value: String(noTime) })
    else chips.push({ label: <>Out in <Term k="Q">{sq ? 'SQ1' : 'Q1'}</Term></>, value: String(headline.qualifying.filter((r) => r.eliminated_in === 'Q1').length) })
  } else if (headline.practice) {
    const p = headline.practice.filter((r) => r.rank).sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0))
    const top = p[0]
    if (top) chips.push({ label: 'Fastest lap', value: fmtMs(top.fastest_lap_ms), color: teamColor(d(top.driver_id)?.team) })
    if (p[9]?.gap_to_fastest_ms != null) chips.push({ label: 'P1 to P10', value: `${fmtMs(p[9].gap_to_fastest_ms)}s` })
    chips.push({ label: 'Set a time', value: `${p.length} of ${Object.keys(headline.drivers).length}` })
  }
  const label = isRaceLike(sessionType) ? (sessionType === 'S' ? 'The sprint' : 'The race') : isQualiLike(sessionType) ? 'Qualifying' : 'This session'
  return (
    <section className="panel p-5 md:p-6 grid md:grid-cols-[1fr_auto] gap-x-10 gap-y-5" aria-label={`${label} in 30 seconds`} data-summary>
      <div>
        <div className="kicker">{label} in 30 seconds</div>
        <ul className="mt-3 space-y-2">
          {sentences.map((s, i) => (
            <li key={i} className={`flex gap-3 ${i === 0 ? 'text-[16px] font-medium' : 'text-[14.5px] t2'}`} data-fact={s.fact ?? undefined}>
              <span className="mt-[9px] h-[5px] w-[5px] rounded-full shrink-0" style={{ background: i === 0 ? 'var(--accent)' : 'var(--text-3)' }} aria-hidden="true" />
              <span>{s.text}</span>
            </li>
          ))}
        </ul>
      </div>
      <dl className="flex md:flex-col gap-3 md:gap-4 overflow-x-auto md:overflow-visible -mx-1 px-1 md:min-w-[11rem]">
        {chips.slice(0, 3).map((c, i) => (
          <div key={i} className="shrink-0 md:border-l md:pl-4 border-[var(--line-2)]">
            <dt className="label">{c.label}</dt>
            <dd className="stat mt-0.5 num" style={c.color ? { boxShadow: `inset 0 -2px 0 ${c.color}` } : undefined}>{c.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

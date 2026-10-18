import type { ReactNode } from 'react'
import { fmtMs, type Headline, type MidfieldStory, type PivotalMoment, type SessionType } from '../../api/client'
import { isQualiLike, isRaceLike, lastName } from '../../lib/f1'
import { teamColor } from '../../lib/teamColors'
import { Term } from '../Glossary'

type Chip = { label: ReactNode; value: string; color?: string }

const NEUTRAL = new Set(['safety_car', 'vsc', 'red_flag'])

function sentenceFromMoments(moments: PivotalMoment[], skip: Set<number>, n: number): string[] {
  const picked = [...moments]
    .filter((m) => m.headline && !NEUTRAL.has(m.moment_type) && m.moment_type !== 'fastest_lap' && m.moment_type !== 'pole' && !(m.driver_id !== null && skip.has(m.driver_id)))
    .sort((a, b) => b.magnitude_score - a.magnitude_score)
    .slice(0, n)
  return picked.map((m) => m.headline!)
}

/** "The race in 30 seconds": three plain sentences and three numbers, built from the computed data
 * (classification, key moments, the midfield spotlight) - nothing here is AI-written. */
export function SessionSummary({ headline, moments, spot, sessionType }: { headline: Headline; moments: PivotalMoment[]; spot?: MidfieldStory | null; sessionType: SessionType }) {
  const d = (id?: number | null) => (id != null ? headline.drivers[String(id)] : undefined)
  const sentences: string[] = []
  const chips: Chip[] = []
  let lead: number | undefined
  if (isRaceLike(sessionType) && headline.race) {
    const fin = headline.race.filter((r) => r.finish_position).sort((a, b) => (a.finish_position ?? 0) - (b.finish_position ?? 0))
    const [w, p2, p3] = fin
    lead = w?.driver_id
    if (w) {
      const from = w.grid_position ? (w.grid_position === 1 ? ' from pole' : ` from P${w.grid_position}`) : ''
      const gap = (p2 as { gap_to_winner_ms?: number | null })?.gap_to_winner_ms
      sentences.push(`${d(w.driver_id)?.name} won${from}${gap ? `, ${(gap / 1000).toFixed(3)}s ahead of ${lastName(d(p2?.driver_id)?.name)}` : p2 ? `, ahead of ${lastName(d(p2.driver_id)?.name)}` : ''}${p3 ? ` and ${lastName(d(p3.driver_id)?.name)}` : ''}.`)
    }
    sentences.push(...sentenceFromMoments(moments, new Set([w?.driver_id ?? -1]), 1))
    const laps = Math.max(0, ...headline.race.map((r) => r.laps_completed ?? 0))
    chips.push({ label: 'Laps', value: String(laps) })
    const c = headline.counts
    if (c) chips.push({ label: <><Term k="DNF">DNF</Term> · <Term k="DNS">DNS</Term></>, value: `${c.dnf} · ${c.dns}` })
    const neutral = moments.filter((m) => NEUTRAL.has(m.moment_type))
    const label = neutral.length ? neutral.map((m) => (m.moment_type === 'vsc' ? 'VSC' : m.moment_type === 'safety_car' ? 'SC' : 'Red')).join(' · ') : 'None'
    chips.push({ label: <><Term k="SC">Safety car</Term> periods</>, value: neutral.length ? label : 'None' })
  } else if (isQualiLike(sessionType) && headline.qualifying) {
    const q = headline.qualifying.filter((r) => r.position).sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
    const pole = q[0]
    lead = pole?.driver_id
    const sq = sessionType === 'SQ'
    if (pole) sentences.push(`${d(pole.driver_id)?.name} took pole${q[1]?.gap_to_pole_ms != null ? ` by ${fmtMs(q[1].gap_to_pole_ms)}s from ${lastName(d(q[1].driver_id)?.name)}` : ''}.`)
    sentences.push(...sentenceFromMoments(moments, new Set([pole?.driver_id ?? -1]), 1))
    if (pole?.q3_ms) chips.push({ label: 'Pole lap', value: fmtMs(pole.q3_ms), color: teamColor(d(pole.driver_id)?.team) })
    const p10 = q[9]
    if (p10?.gap_segment === 'Q3' && p10.gap_to_pole_ms != null) chips.push({ label: 'Pole to P10', value: `${fmtMs(p10.gap_to_pole_ms)}s` })
    const noTime = headline.qualifying.filter((r) => r.status_code === 'NO_TIME').length
    if (noTime) chips.push({ label: 'Set no time', value: String(noTime) })
    else chips.push({ label: <>Out in <Term k="Q">{sq ? 'SQ1' : 'Q1'}</Term></>, value: String(headline.qualifying.filter((r) => r.eliminated_in === 'Q1').length) })
  } else if (headline.practice) {
    const p = headline.practice.filter((r) => r.rank).sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0))
    const [top, second] = p
    lead = top?.driver_id
    if (top) sentences.push(`${d(top.driver_id)?.name} set the pace with a ${fmtMs(top.fastest_lap_ms)}${second?.gap_to_fastest_ms != null ? `, ${fmtMs(second.gap_to_fastest_ms)}s clear of ${lastName(d(second.driver_id)?.name)}` : ''}.`)
    sentences.push(...sentenceFromMoments(moments, new Set([top?.driver_id ?? -1]), 1))
    if (top) chips.push({ label: 'Fastest lap', value: fmtMs(top.fastest_lap_ms), color: teamColor(d(top.driver_id)?.team) })
    if (p[9]?.gap_to_fastest_ms != null) chips.push({ label: 'P1 to P10', value: `${fmtMs(p[9].gap_to_fastest_ms)}s` })
    chips.push({ label: 'Set a time', value: `${p.length} of ${Object.keys(headline.drivers).length}` })
  }
  // one line from beyond the podium, about someone not already mentioned
  const mentioned = (name: string) => sentences.some((s) => s.includes(name))
  const pickSpot = spot && [{ driver_id: spot.driver_id, driver: spot.driver, reason: spot.reason }, ...spot.runners_up]
    .find((c) => c.driver_id !== lead && !mentioned(c.driver))
  if (pickSpot) {
    const first = pickSpot.reason.split(/(?<=\.)\s+/)[0]
    sentences.push(first.startsWith(pickSpot.driver) ? first : `${pickSpot.driver}: ${first}`)
  }
  const label = isRaceLike(sessionType) ? (sessionType === 'S' ? 'The sprint' : 'The race') : isQualiLike(sessionType) ? 'Qualifying' : 'This session'
  return (
    <section className="panel p-5 md:p-6 grid md:grid-cols-[1fr_auto] gap-x-10 gap-y-5" aria-label={`${label} in 30 seconds`}>
      <div>
        <div className="kicker">{label} in 30 seconds</div>
        <ul className="mt-3 space-y-2">
          {sentences.slice(0, 3).map((s, i) => (
            <li key={i} className={`flex gap-3 ${i === 0 ? 'text-[16px] font-medium' : 'text-[14.5px] t2'}`}>
              <span className="mt-[9px] h-[5px] w-[5px] rounded-full shrink-0" style={{ background: i === 0 ? 'var(--accent)' : 'var(--text-3)' }} aria-hidden="true" />
              <span>{s}</span>
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

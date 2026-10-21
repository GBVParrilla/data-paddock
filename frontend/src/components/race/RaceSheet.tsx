import type { ReactNode } from 'react'
import { fmtMs, type Event as EventRow, type Headline, type PivotalMoment, type RaceControlEvent, type SessionType, type TrackOutline } from '../../api/client'
import { isQualiLike, isRaceLike, shortDate, type Tier } from '../../lib/f1'
import type { Line } from '../../lib/mentions'
import { teamColor } from '../../lib/teamColors'
import { Freshness } from '../Freshness'
import { Term } from '../Glossary'
import { TrackMap, type Pin } from '../TrackMap'
import { lapText, momentKind, orderMoments, placeOf } from '../../lib/sheet'

/** The title block: the drawing sheet's own device, in place of meta strings and stat chips. */
function TitleBlock({ event, sessionType, headline, moments }: { event: EventRow; sessionType: SessionType; headline: Headline; moments: PivotalMoment[] }) {
  const rows: [ReactNode, ReactNode][] = [['Round', event.round], ['Date', shortDate(event.event_date)]]
  const d = (id?: number | null) => (id != null ? headline.drivers[String(id)] : undefined)
  if (isRaceLike(sessionType) && headline.race) {
    rows.push(['Laps', Math.max(0, ...headline.race.map((r) => r.laps_completed ?? 0))])
    const win = headline.race.find((r) => r.finish_position === 1)
    if (win) rows.push(['Winner', d(win.driver_id)?.name.split(' ').slice(-1)[0]])
    if (headline.counts) rows.push([<span key="dnf"><Term k="DNF">DNF</Term> and <Term k="DNS">DNS</Term></span>, `${headline.counts.dnf} and ${headline.counts.dns}`])
    const count = (t: string) => moments.filter((m) => m.moment_type === t).length
    const neutral = [[count('red_flag'), 'red'], [count('safety_car'), 'SC'], [count('vsc'), 'VSC']].filter(([n]) => n).map(([n, l]) => `${n} ${l}`)
    rows.push([<Term key="sc" k="SC">Neutralised</Term>, neutral.length ? neutral.join(', ') : 'never'])
  } else if (isQualiLike(sessionType) && headline.qualifying) {
    const pole = headline.qualifying.find((r) => r.position === 1)
    if (pole) rows.push([<Term key="pole" k="pole">Pole</Term>, `${d(pole.driver_id)?.name.split(' ').slice(-1)[0]}${pole.q3_ms ? `, ${fmtMs(pole.q3_ms)}` : ''}`])
    rows.push(['Set no time', headline.qualifying.filter((r) => r.status_code === 'NO_TIME').length])
  } else if (headline.practice) {
    const top = headline.practice.find((r) => r.rank === 1)
    if (top) rows.push(['Fastest', `${d(top.driver_id)?.name.split(' ').slice(-1)[0]}, ${fmtMs(top.fastest_lap_ms)}`])
    rows.push(['Set a time', `${headline.practice.filter((r) => r.rank).length} of ${Object.keys(headline.drivers).length}`])
  }
  return (
    <dl className="title-block w-full sm:w-[15rem]" aria-label="Title block">
      {rows.map(([k, v], i) => <div key={i}><dt>{k}</dt><dd>{v}</dd></div>)}
    </dl>
  )
}

/**
 * The race page's hero, a sheet from an engineer's circuit atlas (REVIEW_ROUND3 D6): the circuit drawn large on
 * a dot grid with registration marks, corner callouts on leader lines, the key moments pinned where they
 * happened (numbered as in the Key moments list), the 30-second summary as the drawing's caption, and the title
 * block in the corner. Picking a driver recolours the drawing by their sector and corner ranks (`overlay`).
 */
export type SheetData = {
  sessionType: SessionType; headline: Headline; sentences: Line[]; moments: PivotalMoment[]; events: RaceControlEvent[]
  overlay?: { sectors?: [Tier, Tier, Tier]; turns?: Record<number, Tier>; below: ReactNode; label: string }
}

export function RaceSheet({ event, outline, data }: { event: EventRow | null; outline: TrackOutline | null; data: SheetData | null }) {
  // One sheet from the first paint, the same elements throughout: the race name shows as soon as the event loads and
  // stays the same <h1> while the rest arrives (it is the page's largest text), and the loading sheet holds the usual
  // height so nothing below moves.
  const moments = data?.moments ?? []
  const ordered = orderMoments(moments)
  const placed = ordered.map((m, i) => ({ m, n: i + 1, at: placeOf(m, data?.events ?? [], outline) }))
  const pins: Pin[] = placed.filter((p) => p.at !== null).map((p) => ({ n: p.n, at: p.at as number | 'pit', label: `${lapText(p.m)}: ${p.m.headline ?? p.m.description}` }))
  const margin = placed.filter((p) => p.at === null)
  const h = data?.headline
  const leader = h?.race?.find((r) => r.finish_position === 1)?.driver_id ?? h?.qualifying?.find((r) => r.position === 1)?.driver_id ?? h?.practice?.find((r) => r.rank === 1)?.driver_id
  const label = !data ? '' : isRaceLike(data.sessionType) ? (data.sessionType === 'S' ? 'The sprint' : 'The race') : isQualiLike(data.sessionType) ? 'Qualifying' : 'This session'
  return (
    <section className={`sheet px-4 sm:px-6 pt-5 pb-5 ${data ? '' : 'h-[840px] lg:h-[610px] overflow-hidden'}`} aria-label={data ? `${label} in 30 seconds` : undefined} aria-busy={!data || undefined} data-summary={data ? '' : undefined}>
      <span className="reg-tr" aria-hidden="true" /><span className="reg-bl" aria-hidden="true" />
      <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-x-8 gap-y-4">
        <div className="min-w-0 flex flex-col">
          <h1 className="h-feature">{event?.name ?? '\u00a0'}</h1>
          <p className="t2 mt-2 text-[13px]">{event ? [event.circuit_name, event.country].filter(Boolean).join(', ') : '\u00a0'}</p>
          {data && (
            <ol className="mt-5 space-y-2.5" aria-label={`${label} in 30 seconds`}>
              {data.sentences.map((s, i) => (
                <li key={i} className={i === 0 ? 'text-[17px] font-semibold leading-snug' : 'text-[14.5px] t2'} data-fact={s.fact ?? undefined}>{s.text}</li>
              ))}
            </ol>
          )}
          {margin.length > 0 && (
            <ul className="mt-5 space-y-1 text-[12.5px] t2" aria-label="Key moments without a place on the drawing">
              {margin.map((p) => (
                <li key={p.n} className="flex gap-2"><span className="num font-bold w-5 shrink-0" style={{ color: 'var(--ink)' }}>{p.n}</span><span>{[lapText(p.m), momentKind(p.m.moment_type)].filter(Boolean).join(', ')}</span></li>
              ))}
            </ul>
          )}
        </div>
        {data && event && (
          <section className="min-w-0 relative" aria-label="Circuit">
            {data.overlay && <h2 className="h2 mb-1">{data.overlay.label}</h2>}
            {outline
              ? <TrackMap key={event.id} outline={outline} callouts pins={pins} sectors={data.overlay?.sectors} turns={data.overlay?.turns} trace={data.overlay ? undefined : leader ? teamColor(data.headline.drivers[String(leader)]?.team) : undefined}
                  stroke={11} plainColor="var(--ink)" className="w-full max-h-[520px]" />
              : <div className="skeleton h-[320px]" />}
            {data.overlay?.below}
          </section>
        )}
      </div>
      {data && event && (
        <div className="mt-4 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <Freshness />
          <TitleBlock event={event} sessionType={data.sessionType} headline={data.headline} moments={data.moments} />
        </div>
      )}
    </section>
  )
}

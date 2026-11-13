import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api, type Event } from '../api/client'
import { Freshness } from '../components/Freshness'
import { PodiumChips } from '../components/RaceCard'
import { TrackMap } from '../components/TrackMap'
import { useTitle } from '../hooks/useTitle'
import { useFetch } from '../hooks/useFetch'
import { shortDate } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { SpoilerGate, usePrefs } from '../state/prefs'
import { useStore } from '../state/store'


/** A round drawn as a plate from the atlas: the circuit large in the winner's team colour, the race name, the podium.
 * The latest round also carries its midfield story. */
function CircuitPlate({ event, latest }: { event: Event; latest?: boolean }) {
  const { hidden } = usePrefs()
  const secret = hidden(event.round)
  const sessions = useFetch((s) => api.sessions(event.id, s), [event.id], !!latest)
  const race = sessions.data?.find((s) => s.session_type === 'R')
  const spot = useFetch((s) => api.midfieldSpotlight(race!.id, false, s), [race?.id], !!latest && !!race)
  const color = event.winner && !secret ? teamColor(event.winner.team) : 'var(--text-3)'
  return (
    <article className="sheet p-4 sm:p-5 flex flex-col min-w-0 w-full" aria-label={latest ? 'Latest race' : `${event.name}, round ${event.round}`}>
      <span className="reg-tr" aria-hidden="true" /><span className="reg-bl" aria-hidden="true" />
      <Link to={`/race/${event.id}${race ? `?session=${race.id}` : ''}`} className="flex flex-col flex-1 group">
        <div className="flex items-baseline justify-between gap-3 label">
          <span className="num">Round {event.round}{latest ? ', the latest' : ''}</span>
          <span className="num">{shortDate(event.event_date)}</span>
        </div>
        <div className={`${latest ? 'h-52 sm:h-64' : 'h-32 sm:h-36'} my-3 flex items-center justify-center`}>
          {event.outline_preview ? <TrackMap outline={event.outline_preview} stroke={latest ? 12 : 14} plainColor={color} className="w-full h-full" />
            : <span className="label">The map appears once the weekend runs</span>}
        </div>
        <h2 className={`display ${latest ? 'text-[26px]' : 'text-[17px]'} leading-tight group-hover:underline underline-offset-4`}>{event.name}</h2>
        {event.podium?.length && !secret ? <div className="mt-2"><PodiumChips podium={event.podium} /></div> : null}
      </Link>
      {secret && event.podium?.length ? <SpoilerGate className="mt-2" rounds={[event.round]} what="Result hidden." /> : null}
      {latest && !secret && (spot.loading || sessions.loading || spot.data) && (
        <div className="mt-4 pt-3 border-t min-h-[4.6rem]" style={{ borderColor: 'var(--line)' }}>
          {spot.data && <>
            <div className="kicker flex items-center gap-2"><span className="swatch h-3.5" style={{ background: teamColor(spot.data.team) }} />Midfield story</div>
            <MidfieldLine driver={spot.data.driver} reason={spot.data.reason} />
          </>}
        </div>
      )}
    </article>
  )
}

/** The championship as a gap ladder: each driver's distance to the leader, drawn to scale. */
function Championship({ year }: { year: number }) {
  const { hidden, followed } = usePrefs()
  const st = useFetch((s) => api.standings(year, s), [year])
  const secret = (st.data?.rounds ?? []).filter((r) => hidden(r))
  const top = st.data?.drivers.slice(0, 10) ?? []
  // the driver you follow is always on the ladder, after the top ten if need be
  const mine = followed ? st.data?.drivers.find((d) => d.driver_id === followed.id) : undefined
  const rows = mine && !top.includes(mine) ? [...top, mine] : top
  const lead = rows[0]?.points ?? 0
  const maxGap = Math.max(1, ...rows.map((d) => lead - d.points))
  const pts = (p: number) => (p % 1 ? p.toFixed(1) : String(p))
  return (
    <section className="lg:col-span-4 flex flex-col" aria-label="Championship">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="h2">Drivers' championship</h2>
        {st.data && <span className="label">after round {st.data.rounds.length}</span>}
      </div>
      {secret.length > 0 && <SpoilerGate className="mt-4" rounds={secret} what={`The standings include round ${secret[0]}.`} />}
      <ol className={`mt-4 flex-1 ${secret.length ? 'hidden' : ''}`} aria-label="Gap to the leader">
        {rows.map((d, i) => {
          const gap = lead - d.points
          return (
            <li key={d.driver_id} className={`grid grid-cols-[1.5rem_minmax(0,7.5rem)_1fr_3.5rem] items-center gap-2 h-8 border-t first:border-t-0 ${d === mine ? 'font-semibold' : ''}`} style={{ borderColor: d === mine && i >= 10 ? 'var(--ink)' : 'var(--line)' }}
              aria-current={d === mine ? 'true' : undefined} data-followed={d === mine || undefined}>
              <span className="num t3 text-[13px]">{d.position}</span>
              <span className="text-[13px] font-medium truncate flex items-center gap-2"><span className="swatch h-3.5" style={{ background: teamColor(d.team) }} />{d.name.split(' ').slice(-1)[0]}</span>
              <span className="relative h-full" aria-hidden="true">
                {/* the ladder: a rule at the leader, each driver's bar running back by their gap */}
                <span className="absolute left-0 top-1 bottom-1 w-px" style={{ background: 'var(--ink)' }} />
                {i > 0 && <span className="absolute left-0 top-[11px] h-[8px]" style={{ width: `${(gap / maxGap) * 100}%`, background: teamColor(d.team) }} />}
              </span>
              <span className="num text-[13px] text-right font-semibold">{i === 0 ? `${pts(d.points)} pts` : `-${pts(gap)}`}</span>
            </li>
          )
        })}
        {st.loading && Array.from({ length: 10 }).map((_, i) => <li key={i} className="skeleton h-7 mb-1" />)}
      </ol>
      <Link to={`/season/${year}`} className="btn-ghost mt-4 underline underline-offset-4">Full standings</Link>
    </section>
  )
}

export function Home() {
  const { year, setYear } = useStore()
  const seasons = useFetch((s) => api.seasons(s), [])
  useEffect(() => {
    if (year === null && seasons.data?.length) setYear(seasons.data[0].year)
  }, [seasons.data, year, setYear])
  const events = useFetch((s) => api.events(year!, s), [year], year !== null)
  useTitle(year ? `${year} season` : null)
  const all = events.data ?? []
  const started = all.filter((e) => e.completed || e.podium?.length).reverse()
  // the latest four rounds drawn large, then a link to /races (decision D3)
  const latest4 = started.slice(0, 4)
  const upcoming = all.filter((e) => !e.completed)
  return (
    <div className="wrap pt-10">
      <div className="mb-8">
        <h1 className="h1">{year ?? ''} season</h1>
        <p className="t2 mt-2 max-w-2xl text-[15px]">Every driver's weekend, told from the timing data. Pick a race, then a driver, from the championship leader to the back of the grid.</p>
        <Freshness className="mt-3" />
      </div>
      {events.error && <p className="t2">{events.error.message}</p>}

      <div className="grid lg:grid-cols-12 gap-x-10 gap-y-10">
        <section className="lg:col-span-8 min-w-0" aria-label="Results">
          {year !== null && <YourDriver year={year} events={all} />}
          <div className="grid sm:grid-cols-3 gap-5">
            {latest4.map((e, i) => <div key={e.id} className={i === 0 ? 'sm:col-span-3' : 'flex'}><CircuitPlate event={e} latest={i === 0} /></div>)}
            {/* placeholders the plates' own size, so nothing below them moves when they arrive */}
            {!events.data && !events.error && <>
              <div className="skeleton sm:col-span-3 h-[470px] sm:h-[520px]" />
              {[0, 1, 2].map((i) => <div key={i} className="skeleton h-[270px]" />)}
            </>}
          </div>
          {started.length > 4 && <Link to="/races" className="btn-ghost mt-5 underline underline-offset-4">All {started.length} races so far</Link>}
        </section>
        {year !== null && <Championship year={year} />}
      </div>

      {upcoming.length > 0 && (
        <section className="mt-12" aria-label="Upcoming">
          <h2 className="h2 mb-3">Still to come</h2>
          <div className="divide-y border-t" style={{ borderColor: 'var(--line)' }}>
            {upcoming.map((e) => (
              <Link key={e.id} to={`/race/${e.id}`} className="grid grid-cols-[3rem_1fr_auto] sm:grid-cols-[3rem_14rem_1fr_auto] items-center gap-4 px-5 h-12 hover:bg-[var(--hover)] text-[13px]" style={{ borderColor: 'var(--line)' }}>
                <span className="t3 num">R{String(e.round).padStart(2, '0')}</span>
                <span className="font-medium">{e.name}{e.has_sprint ? <span className="t3 font-normal">, sprint</span> : ''}</span>
                <span className="t3 truncate hidden sm:block">{e.circuit_name}</span>
                <span className="t2 num">{shortDate(e.event_date)}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

/** "Isack Hadjar climbed from P22 to P10", with the name in bold: never "Isack Hadjar. Isack Hadjar climbed…" (REVIEW_ROUND3 #57). */
function MidfieldLine({ driver, reason }: { driver: string; reason: string }) {
  const first = reason.split('. ')[0].replace(/\.$/, '')
  if (first.startsWith(driver)) return <p className="mt-2 text-[14px] t2"><span className="font-semibold" style={{ color: 'var(--text)' }}>{driver}</span>{first.slice(driver.length)}.</p>
  return <p className="mt-2 text-[14px]"><span className="font-semibold">{driver}.</span> <span className="t2">{first}.</span></p>
}

/** The driver you follow, first: their latest race and where they stand. Set with Follow on any driver's panel. */
function YourDriver({ year, events }: { year: number; events: Event[] }) {
  const { followed, setFollowed, hidden } = usePrefs()
  const st = useFetch((s) => api.standings(year, s), [year], !!followed)
  if (!followed) return null
  const row = st.data?.drivers.find((d) => d.driver_id === followed.id)
  const last = [...(st.data?.rounds ?? [])].reverse().find((r) => row?.results[String(r)])
  const ev = events.find((e) => e.round === last)
  const res = last != null ? row?.results[String(last)] : undefined
  const secret = hidden(last)
  const standingsHidden = (st.data?.rounds ?? []).some((r) => hidden(r))
  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-5 pb-4 border-b text-[14px]" style={{ borderColor: 'var(--line)' }} aria-label="The driver you follow" role="region">
      <span className="label">Following</span>
      <span className="font-semibold">{followed.name}</span>
      {row && ev && !secret && (
        <Link to={`/race/${ev.id}/driver/${followed.ref}`} className="underline underline-offset-4">
          {ev.name.replace(' Grand Prix', '')}: {res?.position ? `P${res.position}` : res?.status}
        </Link>
      )}
      {row && ev && secret && <Link to={`/race/${ev.id}/driver/${followed.ref}`} className="underline underline-offset-4">{ev.name.replace(' Grand Prix', '')}: the race</Link>}
      {row && !standingsHidden && <span className="t2">P{row.position} in the championship, {row.points % 1 ? row.points.toFixed(1) : row.points} points</span>}
      <button type="button" className="btn-ghost text-[12px] ml-auto" onClick={() => setFollowed(null)}>Stop following</button>
    </div>
  )
}

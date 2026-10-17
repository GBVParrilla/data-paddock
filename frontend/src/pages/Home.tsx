import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api, type Driver, type Event } from '../api/client'
import { TrackMap } from '../components/TrackMap'
import { useFetch } from '../hooks/useFetch'
import { shortDate } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { useStore } from '../state/store'

const short = (name: string) => name.replace(' Grand Prix', '')

function PodiumChips({ podium }: { podium: Driver[] }) {
  return (
    <div className="flex items-center gap-3">
      {podium.map((d, i) => (
        <span key={d.id} className="flex items-center gap-1.5 text-[12.5px]">
          <span className="t3 num">{i + 1}</span>
          <span className="swatch h-3.5" style={{ background: teamColor(d.team) }} />
          <span className={i === 0 ? 'font-semibold' : 't2 font-medium'}>{d.code}</span>
        </span>
      ))}
    </div>
  )
}

/** The most recent race, given the room it deserves: map in the winner's colours, podium, midfield story. */
function LatestRace({ event }: { event: Event }) {
  const outline = useFetch((s) => api.trackOutline(event.id, s), [event.id])
  const sessions = useFetch((s) => api.sessions(event.id, s), [event.id])
  const race = sessions.data?.find((s) => s.session_type === 'R')
  const spot = useFetch((s) => api.midfieldSpotlight(race!.id, false, s), [race?.id], !!race)
  const color = teamColor(event.winner?.team)
  const podium = event.podium ?? []
  return (
    <section className="panel overflow-hidden lg:col-span-8 grid md:grid-cols-[1.05fr_1fr]" aria-label="Latest race">
      <div className="p-6 md:p-8 flex flex-col">
        <div className="kicker">Latest race · Round {event.round}</div>
        <h2 className="h-feature mt-3">{short(event.name)}</h2>
        <div className="t2 mt-2 text-[13px]">{event.circuit_name} · {shortDate(event.event_date)}</div>

        <ol className="mt-7 space-y-2.5">
          {podium.map((d, i) => (
            <li key={d.id} className="flex items-center gap-3">
              <span className="w-5 t3 num text-[13px]">{i + 1}</span>
              <span className="swatch" style={{ background: teamColor(d.team), height: i === 0 ? 26 : 18, width: 4 }} />
              <span className={i === 0 ? 'display text-[20px] font-bold' : 'text-[15px] font-medium'}>{d.name}</span>
              <span className="t3 text-[12.5px] ml-auto">{d.team}</span>
            </li>
          ))}
        </ol>

        {spot.data && (
          <div className="mt-7 pt-5 border-t" style={{ borderColor: 'var(--line)' }}>
            <div className="kicker flex items-center gap-2"><span className="dot" style={{ background: teamColor(spot.data.team) }} />Midfield story</div>
            <p className="mt-2 text-[14px]"><span className="font-semibold">{spot.data.driver}.</span> <span className="t2">{spot.data.reason.split('. ')[0]}.</span></p>
          </div>
        )}

        <div className="mt-auto pt-7">
          <Link to={`/race/${event.id}${race ? `?session=${race.id}` : ''}`} className="btn">Open the race <span aria-hidden="true">→</span></Link>
        </div>
      </div>
      <div className="relative min-h-[280px] flex items-center justify-center p-8 border-t md:border-t-0 md:border-l" style={{ borderColor: 'var(--line)', background: 'var(--panel-2)' }}>
        {outline.data && <TrackMap outline={outline.data} stroke={11} plainColor={color} className="w-full max-h-[380px]" />}
      </div>
    </section>
  )
}

function Championship({ year }: { year: number }) {
  const st = useFetch((s) => api.standings(year, s), [year])
  const rows = st.data?.drivers.slice(0, 8) ?? []
  const max = rows[0]?.points || 1
  return (
    <section className="panel lg:col-span-4 p-6 flex flex-col" aria-label="Championship">
      <div className="flex items-baseline justify-between">
        <div className="kicker">Drivers' championship</div>
        {st.data && <span className="label">After round {st.data.rounds.length}</span>}
      </div>
      <ol className="mt-5 space-y-3.5 flex-1">
        {rows.map((d) => (
          <li key={d.driver_id}>
            <div className="flex items-baseline gap-2 text-[13px]">
              <span className="w-4 t3 num">{d.position}</span>
              <span className="font-medium">{d.name}</span>
              <span className="ml-auto num font-semibold">{d.points % 1 ? d.points.toFixed(1) : d.points}</span>
            </div>
            <div className="ml-6 mt-1.5 h-[5px] rounded-full" style={{ background: 'var(--panel-2)' }}>
              <div className="h-full rounded-full" style={{ width: `${(d.points / max) * 100}%`, background: teamColor(d.team) }} />
            </div>
          </li>
        ))}
        {st.loading && Array.from({ length: 8 }).map((_, i) => <li key={i} className="skeleton h-7" />)}
      </ol>
      <Link to={`/season/${year}`} className="btn-ghost mt-5">Full standings <span aria-hidden="true">→</span></Link>
    </section>
  )
}

function RaceCard({ event }: { event: Event }) {
  const outline = useFetch((s) => api.trackOutline(event.id, s), [event.id])
  const color = event.winner ? teamColor(event.winner.team) : 'var(--text-3)'
  return (
    <Link to={`/race/${event.id}`} className="panel lift flex flex-col p-4" aria-label={`${event.name}, round ${event.round}`}>
      <div className="flex items-center justify-between label">
        <span className="num">R{String(event.round).padStart(2, '0')}{event.has_sprint ? ' · Sprint' : ''}</span>
        <span>{shortDate(event.event_date)}</span>
      </div>
      <div className="h-32 my-4 flex items-center justify-center">
        {outline.data ? <TrackMap outline={outline.data} stroke={13} plainColor={color} className="w-full h-full" /> : <span className="label">{outline.loading ? '' : 'Map pending'}</span>}
      </div>
      <div className="display font-bold text-[17px] leading-tight">{short(event.name)}</div>
      <div className="label mt-0.5 truncate">{event.circuit_name}</div>
      <div className="mt-4 pt-3 border-t" style={{ borderColor: 'var(--line)' }}>
        {event.podium?.length ? <PodiumChips podium={event.podium} /> : <span className="label">Weekend in progress</span>}
      </div>
    </Link>
  )
}

export function Home() {
  const { year, setYear } = useStore()
  const seasons = useFetch((s) => api.seasons(s), [])
  useEffect(() => {
    if (year === null && seasons.data?.length) setYear(seasons.data[0].year)
  }, [seasons.data, year, setYear])
  const events = useFetch((s) => api.events(year!, s), [year], year !== null)
  const all = events.data ?? []
  const started = all.filter((e) => e.completed || e.podium?.length).reverse()
  const latest = all.filter((e) => e.completed).at(-1)
  const upcoming = all.filter((e) => !e.completed)
  return (
    <div className="wrap pt-10">
      <div className="mb-8">
        <h1 className="h1">{year ?? ''} season</h1>
        <p className="t2 mt-2 max-w-2xl text-[15px]">Every driver's weekend, told from the timing data. Pick a race, then a driver, from the championship leader to the back of the grid.</p>
      </div>
      {events.error && <p className="t2">{events.error.message}</p>}

      <div className="grid lg:grid-cols-12 gap-4">
        {latest ? <LatestRace event={latest} /> : events.loading && <div className="panel skeleton lg:col-span-8 h-[460px]" />}
        {year !== null && <Championship year={year} />}
      </div>

      {started.length > 0 && (
        <section className="mt-12" aria-label="Results">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="kicker">Results</h2>
            <span className="label">{started.length} of {all.length} rounds</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {started.map((e) => <RaceCard key={e.id} event={e} />)}
          </div>
        </section>
      )}

      {upcoming.length > 0 && (
        <section className="mt-12" aria-label="Upcoming">
          <h2 className="kicker mb-4">Still to come</h2>
          <div className="panel divide-y" style={{ borderColor: 'var(--line)' }}>
            {upcoming.map((e) => (
              <Link key={e.id} to={`/race/${e.id}`} className="grid grid-cols-[3rem_1fr_auto] sm:grid-cols-[3rem_14rem_1fr_auto] items-center gap-4 px-5 h-12 hover:bg-[var(--hover)] text-[13px]" style={{ borderColor: 'var(--line)' }}>
                <span className="t3 num">R{String(e.round).padStart(2, '0')}</span>
                <span className="font-medium">{short(e.name)}{e.has_sprint ? <span className="t3 font-normal"> · Sprint</span> : ''}</span>
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

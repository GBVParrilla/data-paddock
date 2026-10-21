import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type Event, type StandingRow } from '../api/client'
import { RaceCard } from '../components/RaceCard'
import { useFetch } from '../hooks/useFetch'
import { useTitle } from '../hooks/useTitle'
import { shortDate } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { useStore } from '../state/store'

type Filter = 'all' | 'sprint'

/** Every round of the season. "Follow a team" puts that team's results on every card. */
export function RacesPage() {
  const { year, setYear } = useStore()
  const seasons = useFetch((s) => api.seasons(s), [])
  useEffect(() => {
    if (year === null && seasons.data?.length) setYear(seasons.data[0].year)
  }, [seasons.data, year, setYear])
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<Filter>(params.get('sprint') ? 'sprint' : 'all')
  const team = params.get('team') ?? ''
  const events = useFetch((s) => api.events(year!, s), [year], year !== null)
  const standings = useFetch((s) => api.standings(year!, s), [year], year !== null)
  useTitle(year ? `${year} races${team ? ` · ${team}` : ''}` : null)

  const teams = useMemo(() => (standings.data?.teams ?? []).map((t) => t.team), [standings.data])
  const all = (events.data ?? []).filter((e) => filter === 'all' || e.has_sprint)
  const done = all.filter((e) => e.completed)
  const upcoming = all.filter((e) => !e.completed)

  const teamResults = (e: Event): { d: StandingRow; pos: number | null; status: string | null }[] =>
    (standings.data?.drivers ?? []).flatMap((d) => {
      const r = d.results[String(e.round)]
      return r && r.team === team ? [{ d, pos: r.position, status: r.status }] : []
    }).sort((a, b) => (a.pos ?? 99) - (b.pos ?? 99))

  const pickTeam = (t: string) => {
    const next = new URLSearchParams(params)
    if (t) next.set('team', t)
    else next.delete('team')
    setParams(next, { replace: true })
  }

  return (
    <div className="wrap pt-10">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-7">
        <div>
          <h1 className="h1">{year ?? ''} races</h1>
          <p className="t2 mt-2 text-[14px]">{done.length} of {all.length} rounds run{filter === 'sprint' ? ' (sprint weekends)' : ''}.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="seg" role="group" aria-label="Which rounds">
            <button aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>All rounds</button>
            <button aria-pressed={filter === 'sprint'} onClick={() => setFilter('sprint')}>Sprint weekends</button>
          </div>
          <label className="sr-only" htmlFor="follow-team">Follow a team</label>
          <select id="follow-team" className="btn" value={team} onChange={(e) => pickTeam(e.target.value)}>
            <option value="">Follow a team…</option>
            {teams.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {events.loading && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="panel skeleton h-[280px]" />)}</div>}

      {done.length > 0 && (
        <section aria-label="Results">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...done].reverse().map((e) => (
              <RaceCard key={e.id} event={e} footer={team ? (
                <div className="flex items-center gap-3 text-[12.5px]">
                  <span className="swatch h-3.5" style={{ background: teamColor(team) }} />
                  {teamResults(e).map((r) => <span key={r.d.driver_id}><span className="font-semibold">{r.d.code}</span> <span className="t2 num">{r.pos ? `P${r.pos}` : r.status}</span></span>)}
                </div>
              ) : undefined} />
            ))}
          </div>
        </section>
      )}

      {upcoming.length > 0 && (
        <section className="mt-12" aria-label="Upcoming">
          <h2 className="kicker mb-4">Still to come</h2>
          <div className="panel divide-y" style={{ borderColor: 'var(--line)' }}>
            {upcoming.map((e) => (
              <Link key={e.id} to={`/race/${e.id}`} className="grid grid-cols-[3rem_1fr_auto] sm:grid-cols-[3rem_16rem_1fr_auto] items-center gap-4 px-5 h-12 hover:bg-[var(--hover)] text-[13px]" style={{ borderColor: 'var(--line)' }}>
                <span className="t3 num">R{String(e.round).padStart(2, '0')}</span>
                <span className="font-medium truncate">{e.name}{e.has_sprint ? <span className="t3 font-normal">, sprint</span> : ''}</span>
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

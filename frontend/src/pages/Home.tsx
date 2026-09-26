import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api, type Event } from '../api/client'
import { TrackOutline } from '../components/TrackOutline'
import { useFetch } from '../hooks/useFetch'
import { useStore } from '../state/store'

function TrackCard({ event }: { event: Event }) {
  const outline = useFetch((s) => api.trackOutline(event.id, s), [event.id])
  return (
    <Link
      to={`/race/${event.id}`}
      className="card p-3 flex flex-col items-center transition-all hover:-translate-y-0.5"
      style={{ background: 'var(--surface-1)', borderTop: '3px solid var(--accent)' }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 0 0 1px var(--accent), 0 8px 24px -8px var(--accent)')}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '')}
    >
      <div className="w-full flex items-center justify-center px-1">
        {outline.data ? (
          <TrackOutline outline={outline.data} mode={{ kind: 'plain' }} size="100%" showLegend={false} strokeWidth={22} />
        ) : (
          <div className="aspect-square flex items-center justify-center faint text-xs text-center px-4">{outline.loading ? '…' : 'No session data yet'}</div>
        )}
      </div>
      <div className="mt-2 text-center">
        <div className="font-bold text-sm leading-tight">{event.name}</div>
        <div className="faint text-xs">R{event.round} · {event.country}{event.has_sprint ? ' · Sprint' : ''}{event.event_date ? ` · ${event.event_date.slice(0, 10)}` : ''}</div>
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
  return (
    <div>
      <div className="f1-header">
        <div className="max-w-6xl mx-auto px-4 py-7 flex flex-wrap items-end justify-between gap-4 relative">
          <div>
            <h1 className="display text-4xl sm:text-5xl" style={{ color: 'var(--text-primary)', textShadow: '0 0 30px rgba(225,6,0,0.5)' }}>F1 Tracker</h1>
            <p className="muted text-sm mt-1">Every driver's story, not just the podium. Pick a race.</p>
          </div>
          <div className="flex items-center gap-3 relative">
            <label className="text-sm muted uppercase tracking-wide text-xs font-bold" htmlFor="year">Season</label>
            <select id="year" className="btn" value={year ?? ''} onChange={(e) => setYear(Number(e.target.value))}>
              {seasons.data?.map((s) => <option key={s.id} value={s.year}>{s.year}</option>)}
            </select>
            {year && <Link className="btn" to={`/season/${year}`}>Season story</Link>}
          </div>
        </div>
        <div className="checker-strip" />
      </div>
      <div className="max-w-6xl mx-auto px-4 py-6">
        {events.error && <div style={{ color: 'var(--status-critical)' }}>{events.error.message}</div>}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {events.data?.map((e) => <TrackCard key={e.id} event={e} />)}
        </div>
      </div>
    </div>
  )
}

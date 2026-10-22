import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Driver, Event } from '../api/client'
import { shortDate } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { usePrefs } from '../state/prefs'
import { TrackMap } from './TrackMap'

export function PodiumChips({ podium }: { podium: Driver[] }) {
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

/** A round as a card: its circuit in the winner's colours, the podium (or another footer). */
export function RaceCard({ event, footer }: { event: Event; footer?: ReactNode }) {
  const { hidden } = usePrefs()
  const secret = hidden(event.round) && event.completed
  // spoiler-free: the circuit stays, drawn in ink rather than the winner's colour, and the podium is held back
  const color = event.winner && !secret ? teamColor(event.winner.team) : 'var(--text-3)'
  return (
    <Link to={`/race/${event.id}`} className="lift flex flex-col p-4 border-t-2" style={{ borderColor: 'var(--ink)' }} aria-label={`${event.name}, round ${event.round}`}>
      <div className="flex items-center justify-between label">
        <span className="num">Round {event.round}{event.has_sprint ? ', sprint weekend' : ''}</span>
        <span>{shortDate(event.event_date)}</span>
      </div>
      <div className="h-32 my-4 flex items-center justify-center">
        {event.outline_preview ? <TrackMap outline={event.outline_preview} stroke={13} plainColor={color} className="w-full h-full" /> : <span className="label">Map once the weekend runs</span>}
      </div>
      <div className="display font-bold text-[17px] leading-tight">{event.name}</div>
      <div className="label mt-0.5 truncate">{event.circuit_name}</div>
      <div className="mt-4 pt-3 border-t min-h-[2.4rem]" style={{ borderColor: 'var(--line)' }}>
        {secret ? <span className="label" data-spoiler-hidden>Result hidden (spoiler-free)</span>
          : footer ?? (event.podium?.length ? <PodiumChips podium={event.podium} /> : <span className="label">{event.completed ? '' : 'Still to come'}</span>)}
      </div>
    </Link>
  )
}

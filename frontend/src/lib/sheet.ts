import type { PivotalMoment, RaceControlEvent, TrackOutline } from '../api/client'

const PIT_MOMENTS = new Set(['pit_cycle', 'undercut', 'overcut', 'slow_stop'])

/** Key moments in lap order: the numbers on the drawing and in the Key moments list are the same. */
export function orderMoments(moments: PivotalMoment[]): PivotalMoment[] {
  return [...moments].sort((a, b) => (a.lap_number ?? 9999) - (b.lap_number ?? 9999) || b.magnitude_score - a.magnitude_score)
}

export const lapText = (m: PivotalMoment) => (m.lap_number === 0 ? 'Start' : m.lap_number == null ? '' : `Lap ${m.lap_number}`)

/** Where on the drawing a moment happened, when the data says: a corner race control named on that lap for
 * that driver, or the pit lane for a pit-stop moment. Null otherwise (it sits in the margin). */
export function placeOf(m: PivotalMoment, events: RaceControlEvent[], outline: TrackOutline | null): number | 'pit' | null {
  if (PIT_MOMENTS.has(m.moment_type)) return 'pit'
  if (!outline?.turns?.length || m.lap_number == null) return null
  const ev = events.find((e) => e.turn != null && e.lap_number === m.lap_number && (m.driver_id == null || e.driver_ids.includes(m.driver_id)))
  const turn = ev ? outline.turns.find((t) => t.number === ev.turn) : undefined
  return turn ? turn.index : null
}

const KIND: Record<string, string> = {
  dns: 'did not start', dnf: 'retirement', recovery: 'recovery', drop: 'lost places', grid: 'grid drop', safety_car: 'Safety Car', vsc: 'VSC',
  red_flag: 'red flag', penalty: 'penalty', lead_change: 'lead change', undercut: 'undercut', overcut: 'overcut', slow_stop: 'slow stop',
  pit_cycle: 'pit stops', incident: 'stewards', fastest_lap: 'fastest lap', pole: 'pole', knocked_out: 'knocked out', no_time: 'no time', cut_line: 'close call',
}
/** A moment's kind in a word or two, for the margin notes beside the drawing (the full line is in Key moments). */
export const momentKind = (t: string) => KIND[t] ?? t.replace(/_/g, ' ')

import type { Driver, HeadlineRace, PositionByLap } from '../api/client'
import { lastName } from './f1'

const TIMES = ['', 'once', 'twice']

/**
 * A chart title that says what the chart shows (REVIEW_ROUND2 A5): "Russell led from lap 27",
 * "Norris won from pole after losing the lead twice". Falls back to the plain name when the
 * data doesn't support a clear line.
 */
export function positionsTitle(rows: PositionByLap[], race: HeadlineRace[], drivers: Record<string, Driver>): string {
  const plain = 'Positions by lap'
  const winner = race.find((r) => r.finish_position === 1)
  if (!winner) return plain
  const leader = new Map<number, number>()
  for (const r of rows) if (r.position === 1) leader.set(r.lap_number, r.driver_id)
  const laps = [...leader.keys()].sort((a, b) => a - b)
  if (laps.length < 2) return plain
  const name = lastName(drivers[String(winner.driver_id)]?.name)
  if (!name) return plain
  const led = laps.filter((l) => leader.get(l) === winner.driver_id)
  if (led.length === laps.length) return `${name} led every lap`
  // laps where the winner handed the lead to someone else
  const lost = laps.filter((l, i) => i > 0 && leader.get(laps[i - 1]) === winner.driver_id && leader.get(l) !== winner.driver_id).length
  const fromPole = winner.grid_position === 1 && leader.get(laps[0]) === winner.driver_id
  // one lost lead reads better as "led from lap N"; more than one is the story itself
  if (fromPole && lost > 1) return `${name} won from pole after losing the lead ${TIMES[lost] ?? `${lost} times`}`
  // the lap the winner took the lead for good
  let since = laps[laps.length - 1]
  for (let i = laps.length - 1; i >= 0 && leader.get(laps[i]) === winner.driver_id; i--) since = laps[i]
  return `${name} led from lap ${since}`
}

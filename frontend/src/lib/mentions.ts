import { fmtMs, type Headline, type MidfieldStory, type PivotalMoment, type PositionByLap } from '../api/client'
import { isQualiLike, isRaceLike, lastName } from './f1'

/**
 * One fact, one place (REVIEW_ROUND2 #38). A page-scoped register of what has already been said, keyed by
 * driver and fact kind. The 30-second summary claims first, key moments skip what it said, and midfield
 * items skip both.
 */
export class Mentions {
  private facts = new Set<string>()
  private drivers = new Set<number>()
  claim(fact: string | null, driverIds: (number | null | undefined)[] = []) {
    if (fact) this.facts.add(fact)
    for (const d of driverIds) if (d != null) this.drivers.add(d)
  }
  said(fact: string | null): boolean { return !!fact && this.facts.has(fact) }
  mentioned(driverId: number | null | undefined): boolean { return driverId != null && this.drivers.has(driverId) }
}

// Different panels describe the same thing with different words: a "recovery" moment and a "big mover"
// spotlight are both a climb. Fact kinds collapse them so the register sees one fact.
const KIND: Record<string, string> = {
  recovery: 'climb', big_mover: 'climb', points_from_deep: 'climb',
  fastest: 'pace', midfield_pace: 'pace', long_run_pace: 'pace',
  quali_overperformer: 'quali', midfield_q3: 'quali',
  undercut: 'pit_battle', overcut: 'pit_battle', close_battle: 'battle',
}
const NEUTRAL = new Set(['safety_car', 'vsc', 'red_flag'])

export function factOf(m: PivotalMoment): string {
  const kind = KIND[m.moment_type] ?? m.moment_type
  if (m.driver_id === null) return `session:${kind}:${m.lap_number ?? ''}`
  return kind === 'lead_change' ? `${m.driver_id}:${kind}:${m.lap_number}` : `${m.driver_id}:${kind}`
}

export interface Line { text: string; fact: string | null }
export interface MidfieldItem { driver_id: number; text: string; fact: string }
export interface RacePlan { sentences: Line[]; moments: PivotalMoment[]; midfield: MidfieldItem[] }

const MAX_ROWS = 8

function top5(positions: PositionByLap[], lap: number): string {
  return positions.filter((p) => p.lap_number === lap && p.position !== null && p.position <= 5)
    .sort((a, b) => (a.position ?? 0) - (b.position ?? 0)).map((p) => p.driver_id).join(',')
}

/** The second sentence of a race summary: how the race was won, before who climbed (REVIEW_ROUND2 #39). */
function howItWasWon(h: Headline, moments: PivotalMoment[], positions: PositionByLap[], winner: number, name: (id: number | null) => string): { line: Line; who: number[] } | null {
  const race = h.race ?? []
  const grid = new Map(race.map((r) => [r.driver_id, r.grid_position]))
  // 1. the lead change that decided the win: the winner's last move into the lead
  const leads = moments.filter((m) => m.moment_type === 'lead_change' && m.driver_id === winner).sort((a, b) => (b.lap_number ?? 0) - (a.lap_number ?? 0))
  if (leads[0]) {
    const m = leads[0]
    const how = (m.headline ?? '').includes('pit stops') ? ' through the pit stops' : ''
    return { line: { text: `${lastName(name(winner))} took the lead for good from ${lastName(name(m.related_driver_id))}${how} on lap ${m.lap_number}.`, fact: factOf(m) }, who: [winner, m.related_driver_id ?? -1] }
  }
  // 2. a front-runner who didn't start or didn't finish
  const out = moments.filter((m) => (m.moment_type === 'dnf' || m.moment_type === 'dns') && m.driver_id !== null && (grid.get(m.driver_id) ?? 99) <= 6)
    .sort((a, b) => (grid.get(a.driver_id!) ?? 99) - (grid.get(b.driver_id!) ?? 99))
  if (out[0]?.headline) return { line: { text: out[0].headline, fact: factOf(out[0]) }, who: [out[0].driver_id!] }
  // 3. a red flag or safety car that reshuffled the top five
  for (const m of moments.filter((x) => x.moment_type === 'red_flag' || x.moment_type === 'safety_car').sort((a, b) => (a.lap_number ?? 0) - (b.lap_number ?? 0))) {
    if (m.lap_number == null || !positions.length) continue
    // the lap before it against the first lap after it, so later on-track passes aren't credited to it
    const before = top5(positions, Math.max(1, m.lap_number - 1))
    const after = top5(positions, (m.end_lap ?? m.lap_number) + 1)
    if (before && after && before !== after) {
      const what = m.moment_type === 'red_flag' ? 'A red flag' : 'The safety car'
      const when = m.end_lap && m.end_lap !== m.lap_number ? `on laps ${m.lap_number}–${m.end_lap}` : `on lap ${m.lap_number}`
      return { line: { text: `${what} ${when} reshuffled the top five.`, fact: factOf(m) }, who: [] }
    }
  }
  // 4. the biggest climb
  const climb = moments.filter((m) => m.moment_type === 'recovery' && m.headline).sort((a, b) => b.magnitude_score - a.magnitude_score)[0]
  if (climb) return { line: { text: climb.headline!, fact: factOf(climb) }, who: [climb.driver_id!] }
  return null
}

function bestOther(moments: PivotalMoment[], said: Mentions, skipDriver: number | undefined): PivotalMoment | undefined {
  return [...moments]
    .filter((m) => m.headline && !NEUTRAL.has(m.moment_type) && m.moment_type !== 'fastest_lap' && m.moment_type !== 'pole' && m.driver_id !== skipDriver && !said.said(factOf(m)))
    .sort((a, b) => b.magnitude_score - a.magnitude_score)[0]
}

/** The first sentence or two of a midfield reason, without repeating the driver's name. */
function midfieldText(name: string, reason: string): string {
  const first = reason.split(/(?<=\.)\s+/)[0]
  return first.startsWith(name) ? first : `${name}: ${first}`
}

/**
 * Plans what the top of a session page says, so each fact appears once: the summary's sentences, the key
 * moments it hasn't already covered, and up to two midfield items for drivers nobody has mentioned.
 */
export function planSession(h: Headline, moments: PivotalMoment[], spot: MidfieldStory | null | undefined, sessionType: string, positions: PositionByLap[] = []): RacePlan {
  const said = new Mentions()
  const name = (id: number | null) => (id != null ? h.drivers[String(id)]?.name ?? '' : '')
  const sentences: Line[] = []
  let lead: number | undefined
  const fromMoment = (m: PivotalMoment | undefined) => {
    if (!m?.headline) return
    sentences.push({ text: m.headline, fact: factOf(m) })
    said.claim(factOf(m), [m.driver_id, m.related_driver_id])
  }

  if (isRaceLike(sessionType) && h.race) {
    const fin = h.race.filter((r) => r.finish_position).sort((a, b) => (a.finish_position ?? 0) - (b.finish_position ?? 0))
    const [w, p2, p3] = fin
    if (w) {
      lead = w.driver_id
      const from = w.grid_position ? (w.grid_position === 1 ? ' from pole' : ` from P${w.grid_position}`) : ''
      const gap = (p2 as { gap_to_winner_ms?: number | null } | undefined)?.gap_to_winner_ms
      const rest = gap ? `, ${(gap / 1000).toFixed(3)}s ahead of ${lastName(name(p2.driver_id))}` : p2 ? `, ahead of ${lastName(name(p2.driver_id))}` : ''
      sentences.push({ text: `${name(w.driver_id)} won${from}${rest}${p3 ? ` and ${lastName(name(p3.driver_id))}` : ''}.`, fact: `${w.driver_id}:won` })
      said.claim(`${w.driver_id}:won`, [w.driver_id])
      const how = howItWasWon(h, moments, positions, w.driver_id, name)
      if (how) { sentences.push(how.line); said.claim(how.line.fact, how.who) } else fromMoment(bestOther(moments, said, w.driver_id))
    }
  } else if (isQualiLike(sessionType) && h.qualifying) {
    const q = h.qualifying.filter((r) => r.position).sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
    const pole = q[0]
    if (pole) {
      lead = pole.driver_id
      sentences.push({ text: `${name(pole.driver_id)} took pole${q[1]?.gap_to_pole_ms != null ? ` by ${fmtMs(q[1].gap_to_pole_ms)}s from ${lastName(name(q[1].driver_id))}` : ''}.`, fact: `${pole.driver_id}:pole` })
      said.claim(`${pole.driver_id}:pole`, [pole.driver_id])
    }
    fromMoment(bestOther(moments, said, lead))
  } else if (h.practice) {
    const p = h.practice.filter((r) => r.rank).sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0))
    const [top, second] = p
    if (top) {
      lead = top.driver_id
      sentences.push({ text: `${name(top.driver_id)} set the pace with a ${fmtMs(top.fastest_lap_ms)}${second?.gap_to_fastest_ms != null ? `, ${fmtMs(second.gap_to_fastest_ms)}s clear of ${lastName(name(second.driver_id))}` : ''}.`, fact: `${top.driver_id}:pace` })
      said.claim(`${top.driver_id}:pace`, [top.driver_id])
    }
    fromMoment(bestOther(moments, said, lead))
  }

  // one line from beyond the podium, about someone not already mentioned
  const candidates = spot ? [{ driver_id: spot.driver_id, driver: spot.driver, reason: spot.reason, types: spot.story_types }, ...spot.runners_up.map((r) => ({ driver_id: r.driver_id, driver: r.driver, reason: r.reason, types: r.story_types ?? [] }))] : []
  const spotFact = (c: (typeof candidates)[number]) => `${c.driver_id}:${KIND[c.types[0]] ?? c.types[0] ?? 'midfield'}`
  const third = candidates.find((c) => c.driver_id !== lead && !said.mentioned(c.driver_id) && !said.said(spotFact(c)))
  if (third && sentences.length < 3) {
    sentences.push({ text: midfieldText(third.driver, third.reason), fact: spotFact(third) })
    said.claim(spotFact(third), [third.driver_id])
  }

  // key moments: what the summary hasn't said, neutralisations always kept, at most 8 rows with the midfield items
  const remaining = moments.filter((m) => !said.said(factOf(m)) && !(m.moment_type === 'pole' && said.said(`${m.driver_id}:pole`)) && !((m.moment_type === 'fastest' || m.moment_type === 'midfield_pace') && said.said(`${m.driver_id}:pace`)))
  const byWeight = (a: PivotalMoment, b: PivotalMoment) => Number(NEUTRAL.has(b.moment_type)) - Number(NEUTRAL.has(a.moment_type)) || b.magnitude_score - a.magnitude_score
  const kept = [...remaining].sort(byWeight).slice(0, MAX_ROWS)
  for (const m of kept) said.claim(factOf(m), [m.driver_id, m.related_driver_id])
  const midfield: MidfieldItem[] = []
  const fresh = candidates.filter((c) => c.driver_id !== lead && !said.mentioned(c.driver_id) && !said.said(spotFact(c)))
  // midfield items fill spare rows; they never push out a moment that decided the session
  for (const c of fresh.slice(0, Math.min(2, MAX_ROWS - kept.length))) {
    midfield.push({ driver_id: c.driver_id, text: midfieldText(c.driver, c.reason), fact: spotFact(c) })
    said.claim(spotFact(c), [c.driver_id])
  }
  // ...unless nobody beyond the podium is named yet: the mission stays visible on every race and sprint
  const podium = new Set((h.race ?? []).filter((r) => r.finish_position && r.finish_position <= 3).map((r) => r.driver_id))
  const named = [...sentences.map((l) => Number(l.fact?.split(':')[0])), ...kept.map((m) => m.driver_id), ...midfield.map((x) => x.driver_id)]
  if (isRaceLike(sessionType) && !named.some((d) => d != null && Number.isFinite(d) && !podium.has(d)) && fresh[0]) {
    if (kept.length >= MAX_ROWS) kept.pop() // the lightest moment makes room
    midfield.push({ driver_id: fresh[0].driver_id, text: midfieldText(fresh[0].driver, fresh[0].reason), fact: spotFact(fresh[0]) })
  }
  return { sentences: sentences.slice(0, 3), moments: kept, midfield }
}

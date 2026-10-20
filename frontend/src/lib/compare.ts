import type { Headline, IncidentCase } from '../api/client'

/** The session's running order: classification in a race, position in qualifying, rank in practice.
 * `ran`: false for a car that didn't start or set no time. */
export function sessionOrder(h: Headline): { id: number; ran: boolean }[] {
  if (h.race) {
    return [...h.race].sort((a, b) => (a.classification_order ?? a.finish_position ?? 99) - (b.classification_order ?? b.finish_position ?? 99))
      .map((r) => ({ id: r.driver_id, ran: r.status_code !== 'DNS' }))
  }
  if (h.qualifying) {
    return [...h.qualifying].sort((a, b) => (a.position ?? 99) - (b.position ?? 99)).map((r) => ({ id: r.driver_id, ran: r.status_code !== 'NO_TIME' && r.status_code !== 'DNS' }))
  }
  return [...(h.practice ?? [])].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).map((r) => ({ id: r.driver_id, ran: r.rank !== null }))
}

/** Their teammate that weekend, from the entry list the headline carries (Lawson's at round 12 is Verstappen). */
export function teammateOf(h: Headline, id: number): number | null {
  const team = h.drivers[String(id)]?.team
  if (!team) return null
  const order = sessionOrder(h)
  return order.find((r) => r.id !== id && h.drivers[String(r.id)]?.team === team)?.id ?? null
}

/** Who a driver is compared with by default: the teammate, unless the teammate didn't start or set no
 * time; then the car that finished next to them (behind, else ahead). */
export function defaultVs(h: Headline, id: number): number | null {
  const order = sessionOrder(h)
  const mate = teammateOf(h, id)
  if (mate !== null && order.find((r) => r.id === mate)?.ran) return mate
  const i = order.findIndex((r) => r.id === id)
  const next = order.slice(i + 1).find((r) => r.ran) ?? [...order.slice(0, Math.max(i, 0))].reverse().find((r) => r.ran)
  return next?.id ?? mate
}

export interface CompareOption { id: number; why: string }

/** "Compare with…", in order: teammate, the car ahead at the flag, the car behind, anyone they shared a
 * stewards' case with, then everyone else in session order (REVIEW_ROUND3 D8). */
export function compareOptions(h: Headline, id: number, cases: IncidentCase[] = []): CompareOption[] {
  const order = sessionOrder(h)
  const i = order.findIndex((r) => r.id === id)
  const out: CompareOption[] = []
  const add = (other: number | null | undefined, why: string) => {
    if (other == null || other === id || out.some((o) => o.id === other) || !h.drivers[String(other)]) return
    out.push({ id: other, why })
  }
  const finish = h.race ? 'at the flag' : h.qualifying ? 'in qualifying' : 'on the timesheet'
  add(teammateOf(h, id), 'Teammate')
  if (i > 0) add(order[i - 1].id, `Ahead ${finish}`)
  if (i >= 0 && i < order.length - 1) add(order[i + 1].id, `Behind ${finish}`)
  for (const c of cases) if (c.driver_ids.includes(id)) for (const d of c.driver_ids) add(d, 'Stewards looked at both')
  for (const r of order) add(r.id, '')
  return out
}

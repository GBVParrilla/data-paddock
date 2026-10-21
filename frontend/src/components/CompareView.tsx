import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtMs, STATIC, type Driver, type Headline, type HeadlineQualifying, type IncidentCase } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { compareOptions } from '../lib/compare'
import { StoryMeta } from './StoryMeta'

const last = (d: Driver) => d.name.split(' ').slice(-1)[0]

/** The gap in the last qualifying segment both drivers set a time in, from a's side ("+0.214s": a slower). */
function qualiGap(rows: HeadlineQualifying[], a: number, b: number): { seg: string; ms: number } | null {
  const ra = rows.find((r) => r.driver_id === a), rb = rows.find((r) => r.driver_id === b)
  if (!ra || !rb) return null
  for (const k of [3, 2, 1] as const) {
    const ta = ra[`q${k}_ms`], tb = rb[`q${k}_ms`]
    if (ta && tb) return { seg: `Q${k}`, ms: ta - tb }
  }
  return null
}

const gapText = (ms: number) => `${ms > 0 ? '+' : ms < 0 ? '-' : ''}${fmtMs(Math.abs(ms))}s`

/** Three computed facts side by side, for this session type. */
function facts(h: Headline, quali: HeadlineQualifying[] | null, a: number, b: number): { label: string; a: string; b: string }[] {
  if (h.race) {
    const ra = h.race.find((x) => x.driver_id === a), rb = h.race.find((x) => x.driver_id === b)
    const fin = (r?: typeof ra) => (r?.finish_position ? `P${r.finish_position}` : r?.status_code ?? '–')
    const q = quali ? qualiGap(quali, a, b) : null
    return [
      { label: 'Finish', a: fin(ra), b: fin(rb) },
      { label: q ? `Qualifying (${q.seg})` : 'Qualifying', a: q ? (q.ms <= 0 ? 'Ahead' : gapText(q.ms)) : '–', b: q ? (q.ms >= 0 ? 'Ahead' : gapText(-q.ms)) : '–' },
      { label: 'Stops', a: String(ra?.pit_stop_count ?? '–'), b: String(rb?.pit_stop_count ?? '–') },
    ]
  }
  if (h.qualifying) {
    const pos = (id: number) => { const r = h.qualifying!.find((x) => x.driver_id === id); return r?.position ? `P${r.position}` : r?.status_code === 'NO_TIME' ? 'No time' : '–' }
    const out = (id: number) => h.qualifying!.find((x) => x.driver_id === id)?.eliminated_in ?? 'Q3'
    const q = qualiGap(h.qualifying, a, b)
    return [
      { label: 'Position', a: pos(a), b: pos(b) },
      { label: q ? `Gap in ${q.seg}` : 'Gap', a: q ? (q.ms <= 0 ? 'Ahead' : gapText(q.ms)) : '–', b: q ? (q.ms >= 0 ? 'Ahead' : gapText(-q.ms)) : '–' },
      { label: 'Reached', a: out(a), b: out(b) },
    ]
  }
  const r = (id: number) => h.practice?.find((x) => x.driver_id === id)
  const ga = r(a)?.gap_to_fastest_ms, gb = r(b)?.gap_to_fastest_ms
  return [
    { label: 'Position', a: r(a)?.rank ? `P${r(a)!.rank}` : '–', b: r(b)?.rank ? `P${r(b)!.rank}` : '–' },
    { label: 'Best lap', a: fmtMs(r(a)?.fastest_lap_ms), b: fmtMs(r(b)?.fastest_lap_ms) },
    { label: 'Gap between them', a: ga != null && gb != null ? (ga <= gb ? 'Ahead' : gapText(ga - gb)) : '–', b: ga != null && gb != null ? (gb <= ga ? 'Ahead' : gapText(gb - ga)) : '–' },
  ]
}

/**
 * The vs strip at the foot of a driver's panel (REVIEW_ROUND3 D8): who they're compared with ("Compare with…",
 * teammate by default), three computed facts, the gap between them lap by lap, and the written head-to-head when
 * one exists. Never a second full story: "Read X's story" switches the selection instead.
 */
export function VsStrip({ eventId, sessionId, headline, quali, a, b, colors, cases, onVs, onRead }: {
  eventId: number; sessionId: number; headline: Headline; quali: HeadlineQualifying[] | null; a: Driver; b: Driver; colors: [string, string]
  cases: IncidentCase[]; onVs: (id: number) => void; onRead: (id: number) => void
}) {
  const cmp = useFetch((s) => api.compare(sessionId, a.id, b.id, !STATIC, s), [sessionId, a.id, b.id])
  const gap = cmp.data?.gap_over_time ?? []
  const story = cmp.data?.narrative
  const lim = Math.max(1000, ...gap.map((g) => Math.abs(g.gap_ms)))
  const options = compareOptions(headline, a.id, cases)
  const rows = facts(headline, quali, a.id, b.id)
  return (
    <section className="border-t px-5 py-5" style={{ borderColor: 'var(--line)' }} aria-label={`${a.name} versus ${b.name}`} data-vs={b.id}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="h2 flex items-center gap-2">
          <span className="swatch h-4 w-1" style={{ background: colors[0] }} />{last(a)}
          <span className="label">vs</span>
          <span className="swatch h-4 w-1" style={{ background: colors[1], backgroundImage: `repeating-linear-gradient(180deg, ${colors[1]} 0 4px, transparent 4px 7px)` }} />{last(b)}
        </h3>
        <label className="flex items-center gap-2 text-[13px] min-w-0 max-w-full">
          <span className="label">Compare with</span>
          <select className="btn min-w-0 max-w-[16rem]" value={b.id} onChange={(e) => onVs(Number(e.target.value))} aria-label="Compare with">
            {options.map((o) => (
              <option key={o.id} value={o.id}>{headline.drivers[String(o.id)]?.name}{o.why ? ` (${o.why.toLowerCase()})` : ''}</option>
            ))}
          </select>
        </label>
      </div>

      <dl className="grid grid-cols-3 gap-3 mt-4">
        {rows.map((f) => (
          <div key={f.label} className="min-w-0">
            <dt className="label truncate">{f.label}</dt>
            <dd className="num mt-0.5 text-[14px]"><span className="font-semibold">{f.a}</span> <span className="t3">vs</span> {f.b}</dd>
          </div>
        ))}
      </dl>

      {gap.length > 2 && (
        <div className="mt-4">
          <div className="label mb-1">Gap by lap: above the line, {a.code} is ahead</div>
          <div className="h-28">
            <ResponsiveContainer>
              <LineChart data={gap.map((g) => ({ lap: g.lap, gap: -g.gap_ms }))} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--rule)" strokeDasharray="1 3" vertical={false} />
                <XAxis dataKey="lap" tick={{ fill: 'var(--text-2)', fontSize: 11 }} stroke="var(--ink)" tickLine={false} />
                <YAxis domain={[-lim, lim]} ticks={[-lim, 0, lim]} width={40} tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v > 0 ? '+' : ''}${(v / 1000).toFixed(0)}s`} />
                <ReferenceLine y={0} stroke="var(--ink)" />
                <Tooltip isAnimationActive={false} cursor={{ stroke: 'var(--line-2)' }} content={({ active, payload, label }) => active && payload?.length ? (
                  <div className="tip num"><div className="label">Lap {label}</div>{(() => { const v = Number(payload[0].value); return `${v >= 0 ? a.code : b.code} ahead by ${Math.abs(v / 1000).toFixed(1)}s` })()}</div>
                ) : null} />
                <Line dataKey="gap" stroke={colors[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {story && (
        <div className="mt-4">
          <p className="prose max-w-3xl">{story.comparison_text}</p>
          <div className="mt-3"><StoryMeta info={story} route={`/race/${eventId}?session=${sessionId}&drivers=${a.id}&vs=${b.id}`} story={{ title: `${a.name} vs ${b.name}`, text: story.comparison_text, generatedAt: story.generated_at ?? '' }} /></div>
        </div>
      )}

      <button type="button" className="btn-ghost text-[13px] mt-3" onClick={() => onRead(b.id)}>Read {last(b)}'s story</button>
    </section>
  )
}

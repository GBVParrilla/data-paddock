import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtMs, STATIC, type Comparison, type Driver, type Headline } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { StoryMeta } from './StoryMeta'

function facts(h: Headline, id: number): [string, string][] {
  if (h.race) {
    const r = h.race.find((x) => x.driver_id === id)
    return [['Finish', r?.finish_position ? `P${r.finish_position}` : r?.status_code ?? '–'], ['Grid', r?.grid_position ? `P${r.grid_position}` : r?.status_code === 'DNS' ? '–' : 'Pit lane'], ['Stops', String(r?.pit_stop_count ?? '–')], ['Points', String(r?.points ?? 0)]]
  }
  if (h.qualifying) {
    const r = h.qualifying.find((x) => x.driver_id === id)
    const gapLabel = r?.gap_segment && r.gap_segment !== 'Q3' ? `Gap in ${r.gap_segment}` : 'Gap to pole'
    return [['Position', r?.position ? `P${r.position}` : r?.status_code === 'NO_TIME' ? 'No time' : '–'], [gapLabel, r?.gap_to_pole_ms ? `+${fmtMs(r.gap_to_pole_ms)}` : r?.position === 1 ? 'Pole' : '–'], ['Out in', r?.eliminated_in ?? 'Q3']]
  }
  const r = h.practice?.find((x) => x.driver_id === id)
  return [['Position', r?.rank ? `P${r.rank}` : '–'], ['Best lap', fmtMs(r?.fastest_lap_ms)], ['Gap', r?.gap_to_fastest_ms ? `+${fmtMs(r.gap_to_fastest_ms)}` : '–']]
}

/** For pairs without a written head-to-head: the same comparison in plain computed sentences. */
function ComputedHeadToHead({ a, b, headline, cmp }: { a: Driver; b: Driver; headline: Headline; cmp: Comparison }) {
  const lines: string[] = []
  const last = (d: Driver) => d.name.split(' ').slice(-1)[0]
  if (headline.race) {
    const ra = headline.race.find((r) => r.driver_id === a.id), rb = headline.race.find((r) => r.driver_id === b.id)
    if (ra?.finish_position && rb?.finish_position) {
      const [w, l] = ra.finish_position < rb.finish_position ? [ra, rb] : [rb, ra]
      lines.push(`${last(w.driver_id === a.id ? a : b)} finished ahead, P${w.finish_position} to P${l.finish_position}.`)
    }
    const pa = new Map(cmp.driver_a.position_by_lap.map((p) => [p.lap, p.position])), pb = new Map(cmp.driver_b.position_by_lap.map((p) => [p.lap, p.position]))
    const together = [...pa.entries()].filter(([lap, p]) => pb.has(lap) && Math.abs((pb.get(lap) ?? 0) - p) === 1).length
    if (together) lines.push(`They ran next to each other for ${together} laps.`)
    const stops = (d: typeof cmp.driver_a) => d.stints.length - 1
    const sa = stops(cmp.driver_a), sb = stops(cmp.driver_b)
    const n = (k: number) => (k === 1 ? 'once' : k === 2 ? 'twice' : `${k} times`)
    lines.push(sa === sb ? (sa ? `Both stopped ${n(sa)}.` : 'Neither stopped.') : `${last(a)} ${sa ? `stopped ${n(sa)}` : 'did not stop'}, ${last(b)} ${sb ? n(sb) : 'not at all'}.`)
  } else {
    const rows = (headline.qualifying ?? headline.practice ?? []) as { driver_id: number; position?: number | null; rank?: number | null }[]
    const pos = (id: number) => { const r = rows.find((x) => x.driver_id === id); return r?.position ?? r?.rank ?? null }
    const pa = pos(a.id), pb = pos(b.id)
    if (pa && pb) lines.push(`${last(pa < pb ? a : b)} was ahead, P${Math.min(pa, pb)} to P${Math.max(pa, pb)}.`)
  }
  return (
    <div className="mt-6 pt-5 border-t" style={{ borderColor: 'var(--line)' }}>
      <p className="prose max-w-3xl">{lines.join(' ')}</p>
      <p className="label mt-3">Computed from the timing data. Written head-to-heads cover teammates, cars that finished next to each other and drivers the stewards looked at together.</p>
    </div>
  )
}

export function CompareView({ eventId, sessionId, headline, a, b, colors }: { eventId: number; sessionId: number; headline: Headline; a: Driver; b: Driver; colors: string[] }) {
  const cmp = useFetch((s) => api.compare(sessionId, a.id, b.id, !STATIC, s), [sessionId, a.id, b.id])
  const gap = cmp.data?.gap_over_time ?? []
  const fa = facts(headline, a.id), fb = facts(headline, b.id)
  const story = cmp.data?.narrative
  const lim = Math.max(1000, ...gap.map((g) => Math.abs(g.gap_ms)))
  return (
    <section className="panel" aria-label={`${a.name} versus ${b.name}`}>
      <div className="panel-head">
        <h2 className="h2">Head to head</h2>
      </div>
      <div className="panel-body">
        <div className="grid grid-cols-[1fr_auto_1fr] gap-x-4 items-start">
          {[{ d: a, f: fa, c: colors[0], al: 'text-left' }, null, { d: b, f: fb, c: colors[1], al: 'text-right' }].map((side, i) =>
            side === null ? <div key={i} className="label self-center pt-1">vs</div> : (
              <div key={i} className={side.al}>
                <div className={`flex items-center gap-2 ${i ? 'justify-end' : ''}`}>
                  {!i && <span className="dot" style={{ background: side.c }} />}
                  <span className="h2">{side.d.name}</span>
                  {!!i && <span className="dot" style={{ background: side.c }} />}
                </div>
                <dl className={`mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3 ${i ? 'text-right' : ''}`}>
                  {side.f.map(([k, v]) => (
                    <div key={k}><dt className="label">{k}</dt><dd className="text-[17px] font-semibold num mt-0.5">{v}</dd></div>
                  ))}
                </dl>
              </div>
            ),
          )}
        </div>

        {gap.length > 2 && (
          <div className="mt-6">
            <div className="label mb-2">Gap between them by lap - above the line, {a.code} is ahead</div>
            <div className="h-44">
              <ResponsiveContainer>
                <LineChart data={gap.map((g) => ({ lap: g.lap, gap: -g.gap_ms }))} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="lap" tick={{ fill: 'var(--text-3)', fontSize: 11 }} stroke="var(--line)" tickLine={false} />
                  <YAxis domain={[-lim, lim]} width={40} tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v > 0 ? '+' : ''}${(v / 1000).toFixed(0)}s`} />
                  <ReferenceLine y={0} stroke="var(--line-2)" />
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
          <div className="mt-6 pt-5 border-t" style={{ borderColor: 'var(--line)' }}>
            <p className="prose whitespace-pre-line max-w-3xl">{story.comparison_text}</p>
            <div className="mt-4"><StoryMeta info={story} route={`/race/${eventId}?session=${sessionId}&drivers=${a.id},${b.id}`} story={{ title: `${a.name} vs ${b.name}`, text: story.comparison_text, generatedAt: story.generated_at ?? "" }} /></div>
          </div>
        )}
        {!story && cmp.data && <ComputedHeadToHead a={a} b={b} headline={headline} cmp={cmp.data} />}
      </div>
    </section>
  )
}

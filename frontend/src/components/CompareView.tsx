import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtMs, STATIC, type Driver, type Headline } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { StoryMeta } from './StoryMeta'

function facts(h: Headline, id: number): [string, string][] {
  if (h.race) {
    const r = h.race.find((x) => x.driver_id === id)
    return [['Finish', r?.finish_position ? `P${r.finish_position}` : r?.status ?? '–'], ['Grid', r?.grid_position ? `P${r.grid_position}` : '–'], ['Stops', String(r?.pit_stop_count ?? '–')], ['Points', String(r?.points ?? 0)]]
  }
  if (h.qualifying) {
    const r = h.qualifying.find((x) => x.driver_id === id)
    return [['Position', r?.position ? `P${r.position}` : '–'], ['Gap to pole', r?.gap_to_pole_ms ? `+${fmtMs(r.gap_to_pole_ms)}` : r?.position === 1 ? 'Pole' : '–'], ['Out in', r?.eliminated_in ?? 'Q3']]
  }
  const r = h.practice?.find((x) => x.driver_id === id)
  return [['Position', r?.rank ? `P${r.rank}` : '–'], ['Best lap', fmtMs(r?.fastest_lap_ms)], ['Gap', r?.gap_to_fastest_ms ? `+${fmtMs(r.gap_to_fastest_ms)}` : '–']]
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
            <div className="mt-4"><StoryMeta info={story} route={`/race/${eventId}?session=${sessionId}&drivers=${a.id},${b.id}`} story={{ title: `${a.name} vs ${b.name}`, text: story.comparison_text, generatedAt: story.generated_at }} /></div>
          </div>
        )}
        {!story && cmp.data && STATIC && <p className="label mt-5">Written head-to-heads cover teammates. Pick two teammates to read one.</p>}
      </div>
    </section>
  )
}

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type Driver } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { STATIC } from '../api/client'
import { ErrorNote, LoadingNote, RecapAndAnalysis, StoryFooter } from './NarrativePanel'

export function ComparePanel({ sessionId, eventId, a, b, colors }: { sessionId: number; eventId: number; a: Driver; b: Driver; colors: string[] }) {
  // data first (always available), narrative separately (needs the LLM and may be unavailable)
  const data = useFetch((s) => api.compare(sessionId, a.id, b.id, false, s), [sessionId, a.id, b.id])
  // static site: only stories the pipeline wrote (teammates) exist; the charts work for any pair
  const cmp = useFetch((s) => api.compare(sessionId, a.id, b.id, true, s), [sessionId, a.id, b.id], !STATIC)
  const story = STATIC ? data.data?.narrative : cmp.data?.narrative
  const gap = data.data?.gap_over_time ?? []
  return (
    <div className="card p-4" style={{ borderTop: `4px solid ${colors[0]}` }}>
      <h3 className="mb-1 text-lg">
        <span style={{ color: colors[0] }}>{a.name}</span> <span className="not-italic normal-case text-sm muted">vs</span> <span style={{ color: colors[1] }}>{b.name}</span>
      </h3>
      {gap.length > 1 && (
        <div className="h-48 mb-3">
          <div className="text-[11px] uppercase tracking-wide faint mb-1">Cumulative time gap by lap (positive = {a.code ?? a.name} behind)</div>
          <ResponsiveContainer>
            <LineChart data={gap} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="lap" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} stroke="var(--line)" />
              <YAxis width={44} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} stroke="var(--line)" tickFormatter={(v) => `${(v / 1000).toFixed(0)}s`} />
              <ReferenceLine y={0} stroke="var(--text-muted)" />
              <Tooltip formatter={(v) => [`${(Number(v) / 1000).toFixed(3)}s`, 'gap']} labelFormatter={(l) => `Lap ${l}`} contentStyle={{ background: 'var(--surface-1)', border: '1px solid var(--line)', fontSize: 12 }} />
              <Line type="monotone" dataKey="gap_ms" stroke={colors[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {cmp.loading && <LoadingNote what="the comparison" />}
      {cmp.error && <ErrorNote error={cmp.error} />}
      {story && (
        <RecapAndAnalysis
          recap={story.comparison_text}
          footer={
            <StoryFooter
              info={story}
              route={`/race/${eventId}?session=${sessionId}&drivers=${a.id},${b.id}`}
              story={{ title: `${a.name} vs ${b.name} · ${story.story_key.split('/').slice(1, 3).join(' · ')}`, text: story.comparison_text, generatedAt: story.generated_at }}
              meta="head-to-head"
            />
          }
        />
      )}
      {STATIC && data.data && !story && <p className="faint text-xs">Written head-to-head stories cover teammates; the charts above work for any pair.</p>}
    </div>
  )
}

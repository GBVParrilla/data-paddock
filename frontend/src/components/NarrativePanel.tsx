import { useState } from 'react'
import { api, type Driver } from '../api/client'
import { useFetch } from '../hooks/useFetch'

export function LoadingNote({ what }: { what: string }) {
  return (
    <div className="muted text-sm animate-pulse">
      Generating {what} with Claude… the first request for a driver/session can take a minute; it is cached afterwards.
    </div>
  )
}

export function ErrorNote({ error }: { error: Error }) {
  return <div className="text-sm" style={{ color: 'var(--status-critical)' }}>{error.message}</div>
}

/** Recap = facts. Analysis = hedged inference. Same visual pattern everywhere. */
export function RecapAndAnalysis({ recap, analysis, meta }: { recap: string; analysis?: string; meta?: string }) {
  return (
    <div className="space-y-3">
      <section>
        <h4 className="text-[11px] uppercase tracking-wide faint mb-1">Recap · from timing data</h4>
        <p className="text-sm leading-relaxed whitespace-pre-line">{recap}</p>
      </section>
      {analysis && (
        <section className="analysis rounded-md px-3 py-2">
          <h4 className="text-[11px] uppercase tracking-wide mb-1" style={{ color: 'var(--analysis-border)' }}>Analysis · interpretation, not fact</h4>
          <p className="text-sm leading-relaxed whitespace-pre-line">{analysis}</p>
        </section>
      )}
      {meta && <div className="faint text-[11px]">{meta}</div>}
    </div>
  )
}

export function NarrativePanel({ sessionId, eventId, driver, accent }: { sessionId: number; eventId: number; driver: Driver; accent: string }) {
  const [tab, setTab] = useState<'session' | 'weekend'>('session')
  const story = useFetch((s) => api.narrative(sessionId, driver.id, s), [sessionId, driver.id])
  const arc = useFetch((s) => api.weekendArc(eventId, driver.id, s), [eventId, driver.id, tab], tab === 'weekend')
  return (
    <div className="card p-4" style={{ borderTop: `4px solid ${accent}` }}>
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <h3 className="font-semibold">{driver.name} <span className="muted font-normal text-sm">· {driver.team}</span></h3>
        <div className="flex gap-1">
          <button className="btn" aria-pressed={tab === 'session'} onClick={() => setTab('session')}>Session story</button>
          <button className="btn" aria-pressed={tab === 'weekend'} onClick={() => setTab('weekend')}>Weekend arc</button>
        </div>
      </div>
      {tab === 'session' && (
        <>
          {story.loading && <LoadingNote what="the session story" />}
          {story.error && <ErrorNote error={story.error} />}
          {story.data && <RecapAndAnalysis recap={story.data.narrative_text} analysis={story.data.strategy_analysis_text} meta={`${story.data.model_used} · ${new Date(story.data.generated_at + 'Z').toLocaleString()}`} />}
        </>
      )}
      {tab === 'weekend' && (
        <>
          {arc.loading && <LoadingNote what="the weekend arc (this generates any missing session stories first)" />}
          {arc.error && <ErrorNote error={arc.error} />}
          {arc.data && <RecapAndAnalysis recap={arc.data.arc_text} meta={`How the weekend connected · ${arc.data.model_used}`} />}
        </>
      )}
    </div>
  )
}

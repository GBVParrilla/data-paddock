import { useState, type ReactNode } from 'react'
import { api, STATIC, type Driver, type StoryEditInfo } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { editorMode, editUrl, flagUrl, githubEnabled, pageUrl, revertUrl, type StoryText } from '../lib/stories'

export function LoadingNote({ what }: { what: string }) {
  return (
    <div className="muted text-sm animate-pulse">
      {STATIC ? `Loading ${what}…` : `Loading ${what}… if it hasn't been written yet, Claude writes it now (can take a minute).`}
    </div>
  )
}

/** Provenance + correction links under every AI story. `route` = page that shows this story (for flags). */
export function StoryFooter({ info, story, route, meta }: { info: StoryEditInfo; story: StoryText; route: string; meta?: string }) {
  const editor = editorMode()
  const page = pageUrl(route)
  return (
    <div className="faint text-[11px] flex flex-wrap items-center gap-x-3 gap-y-1">
      <span>{info.edited ? 'Written by Claude · corrected by the editor' : 'Written by Claude from timing data'}{meta ? ` · ${meta}` : ''}</span>
      {info.edited && info.edit_note && <span title="Editor's note">“{info.edit_note}”</span>}
      {githubEnabled && (
        <a className="underline hover:no-underline" href={flagUrl(info, story, page)} target="_blank" rel="noreferrer">Flag a problem</a>
      )}
      {githubEnabled && editor && (
        <>
          <a className="underline font-semibold" style={{ color: 'var(--accent)' }} href={editUrl(info, story)} target="_blank" rel="noreferrer">{info.edited ? 'Edit correction' : 'Edit'}</a>
          {info.edited && <a className="underline" href={revertUrl(info)} target="_blank" rel="noreferrer">Revert to AI</a>}
          <button className="underline" onClick={() => navigator.clipboard?.writeText(info.story_key)} title="Copy the story key (the file name under stories/)">{info.story_key}</button>
        </>
      )}
      {editor && info.edit_stale && (
        <span style={{ color: 'var(--status-critical)' }}>Claude rewrote this story after your correction (its data changed) - review your edit.</span>
      )}
    </div>
  )
}

export function ErrorNote({ error }: { error: Error }) {
  return <div className="text-sm" style={{ color: 'var(--status-critical)' }}>{error.message}</div>
}

/** Recap = facts. Analysis = hedged inference. Same visual pattern everywhere. */
export function RecapAndAnalysis({ recap, analysis, meta, footer }: { recap: string; analysis?: string; meta?: string; footer?: ReactNode }) {
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
      {footer}
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
          {story.data && (
            <RecapAndAnalysis
              recap={story.data.narrative_text}
              analysis={story.data.strategy_analysis_text}
              footer={
                <StoryFooter
                  info={story.data}
                  route={`/race/${eventId}?session=${sessionId}&drivers=${driver.id}`}
                  story={{ title: `${driver.name} · ${story.data.session_type} · ${story.data.story_key.split('/')[1]}`, text: story.data.narrative_text, analysis: story.data.strategy_analysis_text, generatedAt: story.data.generated_at }}
                  meta={new Date(story.data.generated_at + 'Z').toLocaleDateString()}
                />
              }
            />
          )}
        </>
      )}
      {tab === 'weekend' && (
        <>
          {arc.loading && <LoadingNote what="the weekend arc" />}
          {arc.error && <ErrorNote error={arc.error} />}
          {arc.data && (
            <RecapAndAnalysis
              recap={arc.data.arc_text}
              footer={
                <StoryFooter
                  info={arc.data}
                  route={`/race/${eventId}?session=${sessionId}&drivers=${driver.id}`}
                  story={{ title: `${driver.name} · weekend · ${arc.data.story_key.split('/')[1]}`, text: arc.data.arc_text, generatedAt: arc.data.generated_at }}
                  meta="how the weekend connected"
                />
              }
            />
          )}
        </>
      )}
    </div>
  )
}

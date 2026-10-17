import { api, type Driver, type Headline, type SessionRow, type SessionType } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { SESSION_SHORT, SESSION_TINY } from '../lib/f1'
import { StoryMeta } from './StoryMeta'

function resultIn(h: Headline, id: number): string {
  if (h.race) {
    const r = h.race.find((x) => x.driver_id === id)
    if (!r) return '–'
    return r.finish_position ? `P${r.finish_position}` : 'DNF'
  }
  const rows = h.practice ?? h.qualifying ?? []
  const r = rows.find((x) => x.driver_id === id) as { rank?: number | null; position?: number | null } | undefined
  const p = r?.rank ?? r?.position
  return p ? `P${p}` : '–'
}

/** One driver through the weekend: result in each session (click to switch), then the story. */
export function DriverStory({ eventId, sessionId, sessions, driver, color, onSession }: {
  eventId: number
  sessionId: number
  sessions: SessionRow[]
  driver: Driver
  color: string
  onSession: (id: number) => void
}) {
  const ready = sessions.filter((s) => s.ingestion.transforms)
  const results = useFetch((s) => Promise.all(ready.map((x) => api.headline(x.id, s))), [ready.map((x) => x.id).join(',')], ready.length > 0)
  const story = useFetch((s) => api.narrative(sessionId, driver.id, s), [sessionId, driver.id])
  const arc = useFetch((s) => api.weekendArc(eventId, driver.id, s), [eventId, driver.id])
  const current = sessions.find((s) => s.id === sessionId)
  const route = `/race/${eventId}?session=${sessionId}&drivers=${driver.id}`

  return (
    <section className="panel overflow-hidden" aria-label={`${driver.name}'s weekend`}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
        <div className="flex items-center gap-3">
          <span className="swatch h-8 w-1" style={{ background: color }} />
          <div>
            <div className="h2">{driver.name}</div>
            <div className="label">{driver.team}{driver.number ? ` · #${driver.number}` : ''}</div>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1" role="tablist" aria-label="Sessions">
          {ready.map((s, i) => {
            const on = s.id === sessionId
            const res = results.data?.[i] ? resultIn(results.data[i], driver.id) : ''
            return (
              <button key={s.id} role="tab" aria-selected={on} onClick={() => onSession(s.id)}
                className={`px-3 py-1.5 rounded-lg text-left border ${on ? 'bg-[var(--panel-2)] border-[var(--line-2)]' : 'border-transparent hover:bg-[var(--hover)]'}`}>
                <div className="text-[11px] t3 font-medium">{SESSION_TINY[s.session_type as SessionType]}</div>
                <div className="text-[13px] font-semibold num min-w-[2.2rem]">{res || ' '}</div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="px-5 py-5">
        {story.loading && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-4" style={{ width: `${90 - i * 12}%` }} />)}</div>}
        {story.error && <p className="t2">{story.error.message}</p>}
        {story.data && (
          <div className="grid lg:grid-cols-2 gap-x-10 gap-y-6">
            <div>
              <h3 className="label mb-2">{current ? SESSION_SHORT[current.session_type as SessionType] : ''} · what happened</h3>
              <p className="prose whitespace-pre-line">{story.data.narrative_text}</p>
            </div>
            <div>
              <h3 className="label mb-2 flex items-center gap-2">
                Strategy analysis
                <span className="chip !text-[11px] !py-0" title="Inference from the data, not established fact">Interpretation</span>
              </h3>
              <p className="prose-2 whitespace-pre-line">{story.data.strategy_analysis_text}</p>
            </div>
          </div>
        )}
        {arc.data && (
          <div className="mt-6 pt-5 border-t" style={{ borderColor: 'var(--line)' }}>
            <h3 className="label mb-2">The weekend in context</h3>
            <p className="prose-2 whitespace-pre-line max-w-3xl">{arc.data.arc_text}</p>
          </div>
        )}
        {story.data && (
          <div className="mt-6">
            <StoryMeta info={story.data} route={route} story={{ title: `${driver.name} · ${current?.session_type} · ${story.data.story_key.split('/')[1]}`, text: story.data.narrative_text, analysis: story.data.strategy_analysis_text, generatedAt: story.data.generated_at }} />
          </div>
        )}
      </div>
    </section>
  )
}

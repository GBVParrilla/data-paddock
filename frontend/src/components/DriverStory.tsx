import type { ReactNode } from 'react'
import { api, type Driver, type Headline, type SessionRow, type SessionType, type WeekendArc } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { SESSION_SHORT, SESSION_TINY } from '../lib/f1'
import { useMode } from '../state/mode'
import { asSource, useStorySource } from '../state/sources'
import { Term } from './Glossary'
import { Debrief } from './Debrief'
import { StoryMeta } from './StoryMeta'

function resultIn(h: Headline, id: number): string {
  if (h.race) {
    const r = h.race.find((x) => x.driver_id === id)
    if (!r) return '–'
    return r.finish_position ? `P${r.finish_position}` : r.status_code
  }
  const rows = h.practice ?? h.qualifying ?? []
  const r = rows.find((x) => x.driver_id === id) as { rank?: number | null; position?: number | null; status_code?: string | null } | undefined
  const p = r?.rank ?? r?.position
  return p ? `P${p}` : r?.status_code === 'NO_TIME' ? 'No time' : '–'
}

/** The weekend in a paragraph, under the session strip. It counts towards the page's source line. */
function WeekendLine({ arc }: { arc: WeekendArc }) {
  const source = asSource(arc.source, arc.edited)
  const badge = useStorySource(source)
  return (
    <p className="px-5 py-3 text-[13.5px] t2 border-b max-w-none" style={{ borderColor: 'var(--line)' }} data-story-source={source}>
      <span className="label mr-2">The weekend</span>{arc.arc_text}
      {badge && <span className="chip !py-0 ml-2 align-middle">{badge}</span>}
    </p>
  )
}

/** One driver through the weekend: result in each session (click to switch), then the story, then the vs strip
 * (`children`). Essential: the verdict headline, what happened, up to three numbers. Expert: the same headline over
 * the engineer's debrief computed in code, instead of more prose (REVIEW_ROUND3 D7). */
export function DriverStory({ eventId, sessionId, sessions, driver, color, onSession, children }: {
  eventId: number
  sessionId: number
  sessions: SessionRow[]
  driver: Driver
  color: string
  onSession: (id: number) => void
  children?: ReactNode
}) {
  const { expert } = useMode()
  const ready = sessions.filter((s) => s.ingestion.transforms)
  const results = useFetch((s) => Promise.all(ready.map((x) => api.headline(x.id, s))), [ready.map((x) => x.id).join(',')], ready.length > 0)
  const story = useFetch((s) => api.narrative(sessionId, driver.id, s), [sessionId, driver.id])
  const arc = useFetch((s) => api.weekendArc(eventId, driver.id, s), [eventId, driver.id])
  const current = sessions.find((s) => s.id === sessionId)
  const route = `/race/${eventId}?session=${sessionId}&drivers=${driver.id}`
  const debrief = expert ? story.data?.debrief : null

  return (
    <section className="panel overflow-hidden" aria-label={`${driver.name}'s weekend`}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
        <div className="flex items-center gap-3">
          <span className="swatch h-8 w-1" style={{ background: color }} />
          <div>
            <div className="h2">{driver.name}</div>
            <div className="label">{driver.team}{driver.number ? ` · #${driver.number}` : ''}{driver.stand_in && <> · <Term k="standin">stand-in</Term> (usually {driver.usual_team})</>}</div>
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
                <div className="text-[13px] font-semibold num min-w-[2.2rem]">{res || ' '}</div>
              </button>
            )
          })}
        </div>
      </div>

      {arc.data && <WeekendLine arc={arc.data} />}

      <div className="px-5 py-5">
        {story.loading && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-4" style={{ width: `${90 - i * 12}%` }} />)}</div>}
        {story.error && <p className="t2">{story.error.message}</p>}
        {story.data && (
          <div className="max-w-3xl">
            <div className="kicker">{current ? SESSION_SHORT[current.session_type as SessionType] : ''}</div>
            {story.data.headline && <h3 className="display font-bold text-[22px] leading-tight mt-1.5">{story.data.headline}</h3>}
            {debrief ? <Debrief d={debrief} /> : (
              <>
                {story.data.summary && <p className="text-[15.5px] mt-2.5 leading-relaxed" data-essential>{story.data.summary}</p>}
                {!!story.data.key_numbers?.length && (
                  <dl className="flex flex-wrap gap-x-6 gap-y-3 mt-4">
                    {story.data.key_numbers.slice(0, 3).map((k) => (
                      <div key={k.label}><dt className="label">{k.label}</dt><dd className="stat num !text-[19px] mt-0.5">{k.value}</dd></div>
                    ))}
                  </dl>
                )}
              </>
            )}
          </div>
        )}
        {story.data && (
          <div className="mt-6">
            <StoryMeta info={story.data} route={route} story={{ title: `${driver.name} · ${current?.session_type} · ${story.data.story_key.split('/')[1]}`, text: story.data.summary ?? '', generatedAt: story.data.generated_at ?? '' }} />
          </div>
        )}
      </div>
      {children}
    </section>
  )
}

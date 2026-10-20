import { api, type Driver, type Headline, type SessionRow, type SessionType, type WeekendArc } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { nth, SESSION_SHORT, SESSION_TINY } from '../lib/f1'
import { useMode } from '../state/mode'
import { asSource, useStorySource } from '../state/sources'
import { Term } from './Glossary'
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

/** One driver through the weekend: result in each session (click to switch), then the story.
 * Essential: verdict headline, what happened, up to three numbers. Expert: the full story, every key number
 * and the sector ranks inline (decision D5). */
export function DriverStory({ eventId, sessionId, sessions, driver, color, onSession, sectorRanks }: {
  eventId: number
  sessionId: number
  sessions: SessionRow[]
  driver: Driver
  color: string
  onSession: (id: number) => void
  sectorRanks?: { sec: number; rank: number; of: number }[] | null
}) {
  const { expert } = useMode()
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
                <div className="text-[13px] font-semibold num min-w-[2.2rem]">{res || ' '}</div>
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
          <div className="grid lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-x-10 gap-y-6">
            <div>
              <div className="kicker">{current ? SESSION_SHORT[current.session_type as SessionType] : ''}</div>
              {story.data.headline && <h3 className="display font-bold text-[22px] leading-tight mt-1.5">{story.data.headline}</h3>}
              {story.data.summary && <p className="text-[15.5px] mt-2.5 leading-relaxed">{story.data.summary}</p>}
              {!!story.data.key_numbers?.length && (
                <dl className="flex flex-wrap gap-x-6 gap-y-3 mt-4">
                  {story.data.key_numbers.slice(0, expert ? undefined : 3).map((k) => (
                    <div key={k.label}><dt className="label">{k.label}</dt><dd className="stat num !text-[19px] mt-0.5">{k.value}</dd></div>
                  ))}
                </dl>
              )}
              {expert && sectorRanks && (
                <p className="text-[13px] t2 mt-3" data-expert="sector-ranks">
                  <span className="label mr-2">Sectors</span>
                  {sectorRanks.map((r) => `S${r.sec} ${nth(r.rank)}`).join(' · ')} <span className="t3">of {sectorRanks[0].of} who set a time</span>
                </p>
              )}
              {story.data.narrative_text && (  // prompt v4 stories have none: Expert is the computed debrief (REVIEW_ROUND3 D7)
              <details key={`${story.data.story_key}-${expert}`} className="mt-5 group" open={expert || !story.data.summary}>
                <summary className="cursor-pointer list-none text-[13px] font-medium inline-flex items-center gap-1.5 hover:text-[var(--text)] t2">
                  <span className="group-open:hidden">Read the full story</span><span className="hidden group-open:inline">Hide the full story</span>
                  <span aria-hidden="true" className="transition-transform group-open:rotate-90">›</span>
                </summary>
                <div className="prose mt-3 space-y-3">{story.data.narrative_text.split(/\n\s*\n/).map((p, i) => <p key={i}>{p}</p>)}</div>
              </details>
              )}
            </div>
            {story.data.strategy_analysis_text && (
              <div className="lg:border-l lg:pl-8" style={{ borderColor: 'var(--line)' }}>
                <h3 className="label mb-2 flex items-center gap-2">
                  Analysis
                  <span className="chip !text-[11px] !py-0"><Term k="interpretation">Interpretation</Term></span>
                </h3>
                <p className="prose-2">{story.data.strategy_analysis_text}</p>
              </div>
            )}
          </div>
        )}
        {story.data && (
          <div className="mt-6">
            <StoryMeta info={story.data} route={route} story={{ title: `${driver.name} · ${current?.session_type} · ${story.data.story_key.split('/')[1]}`, text: story.data.narrative_text, analysis: story.data.strategy_analysis_text, generatedAt: story.data.generated_at ?? '' }} />
          </div>
        )}
      </div>
    </section>
  )
}

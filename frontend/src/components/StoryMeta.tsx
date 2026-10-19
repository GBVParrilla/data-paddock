import type { StoryEditInfo } from '../api/client'
import { editorMode, editUrl, flagUrl, githubEnabled, pageUrl, revertUrl, type StoryText } from '../lib/stories'
import { asSource, useStorySource } from '../state/sources'

// Optional: an address for readers without a GitHub account (repository variable VITE_REPORT_EMAIL).
const REPORT_EMAIL = import.meta.env.VITE_REPORT_EMAIL as string | undefined

function mailUrl(info: StoryEditInfo, story: StoryText, page: string): string {
  const body = `Story: ${story.title}\nPage: ${page}\nStory id: ${info.story_key}\n\nWhat's wrong:\n`
  return `mailto:${REPORT_EMAIL}?subject=${encodeURIComponent(`Data Paddock correction: ${story.title}`)}&body=${encodeURIComponent(body)}`
}

/** Correction links under a story, and a source badge only when this story differs from the page's
 * source line (an edited story, or a computed one among Claude-written ones). Editor links in editor mode. */
export function StoryMeta({ info, story, route }: { info: StoryEditInfo & { source?: string }; story: StoryText; route: string }) {
  const editor = editorMode()
  const page = pageUrl(route)
  const source = asSource(info.source, info.edited)
  const badge = useStorySource(source)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] t3" data-story-source={source}>
      {badge && <span className="chip !py-0">{badge}</span>}
      {info.edited && info.edit_note && <span className="t2">Note: {info.edit_note}</span>}
      {REPORT_EMAIL && <a className="hover:text-[var(--text)] underline-offset-2 hover:underline" href={mailUrl(info, story, page)}>Report an error</a>}
      {githubEnabled && <a className="hover:text-[var(--text)] underline-offset-2 hover:underline" href={flagUrl(info, story, page)} target="_blank" rel="noreferrer">{REPORT_EMAIL ? 'Report on GitHub' : 'Report an error'}</a>}
      {githubEnabled && editor && (
        <>
          <a className="text-[var(--text)] underline underline-offset-2" href={editUrl(info, story)} target="_blank" rel="noreferrer">{info.edited ? 'Edit correction' : 'Edit'}</a>
          {info.edited && <a className="underline underline-offset-2" href={revertUrl(info)} target="_blank" rel="noreferrer">Revert to AI</a>}
          <span className="font-mono text-[11px]">{info.story_key}</span>
        </>
      )}
      {editor && info.edit_stale && <span style={{ color: 'var(--yellow)' }}>Story was rewritten after your correction - please review</span>}
    </div>
  )
}

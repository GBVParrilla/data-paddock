import type { StoryEditInfo } from '../api/client'
import { editorMode, editUrl, flagUrl, githubEnabled, pageUrl, revertUrl, type StoryText } from '../lib/stories'

// Optional: an address for readers without a GitHub account (repository variable VITE_REPORT_EMAIL).
const REPORT_EMAIL = import.meta.env.VITE_REPORT_EMAIL as string | undefined

const SOURCE_TEXT: Record<string, string> = {
  claude: 'Written by Claude from the timing data, then fact-checked against it',
  template: 'Written from the timing data (every figure computed, no AI text)',
  edited: 'Corrected by the editor',
}

function mailUrl(info: StoryEditInfo, story: StoryText, page: string): string {
  const body = `Story: ${story.title}\nPage: ${page}\nStory id: ${info.story_key}\n\nWhat's wrong:\n`
  return `mailto:${REPORT_EMAIL}?subject=${encodeURIComponent(`Data Paddock correction: ${story.title}`)}&body=${encodeURIComponent(body)}`
}

/** Provenance + correction links under a story: quiet by default, editor links in editor mode. */
export function StoryMeta({ info, story, route }: { info: StoryEditInfo & { source?: string }; story: StoryText; route: string }) {
  const editor = editorMode()
  const page = pageUrl(route)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] t3">
      <span>{SOURCE_TEXT[info.edited ? 'edited' : info.source ?? 'claude']}</span>
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

import type { StoryEditInfo } from '../api/client'
import { editorMode, editUrl, flagUrl, githubEnabled, pageUrl, revertUrl, type StoryText } from '../lib/stories'

/** Provenance + correction links under a story: quiet by default, editor links in editor mode. */
export function StoryMeta({ info, story, route }: { info: StoryEditInfo; story: StoryText; route: string }) {
  const editor = editorMode()
  const page = pageUrl(route)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] t3">
      <span>{info.edited ? 'Written by Claude from timing data · corrected by the editor' : 'Written by Claude from timing data'}</span>
      {info.edited && info.edit_note && <span className="t2">Note: {info.edit_note}</span>}
      {githubEnabled && <a className="hover:text-[var(--text)] underline-offset-2 hover:underline" href={flagUrl(info, story, page)} target="_blank" rel="noreferrer">Report an error</a>}
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

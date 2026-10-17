/**
 * Story corrections, GitHub-backed (works on the static site - no server needed):
 * - anyone can "Flag a problem": opens a prefilled GitHub issue (template: .github/ISSUE_TEMPLATE/story-flag.yml)
 * - the editor (repo owner) turns on editor mode with ?editor=1 and gets "Edit" buttons that open
 *   stories/<story_key>.md in GitHub's web editor, prefilled with the AI text. Committing it rebuilds
 *   the site with the correction; deleting the file reverts to the AI version.
 */
import type { StoryEditInfo } from '../api/client'

const REPO = (import.meta.env.VITE_GITHUB_REPO as string | undefined) ?? ''
const BRANCH = (import.meta.env.VITE_GITHUB_BRANCH as string | undefined) ?? 'main'
const EDITOR_KEY = 'f1tracker:editor-mode'

export const githubEnabled = REPO !== ''

/** `?editor=1` / `?editor=0` anywhere in the URL (hash routes included) toggles it; remembered per browser. */
export function editorMode(): boolean {
  const m = window.location.href.match(/[?&]editor=([01])/)
  try {
    if (m) localStorage.setItem(EDITOR_KEY, m[1])
    return (m ? m[1] : localStorage.getItem(EDITOR_KEY)) === '1'
  } catch {
    return m?.[1] === '1'
  }
}

export function setEditorMode(on: boolean): void {
  try {
    localStorage.setItem(EDITOR_KEY, on ? '1' : '0')
  } catch {
    /* ignore */
  }
}

/** Link to the page a story is shown on, with the selection that shows it. `route` is e.g. `/race/3?session=5&drivers=1`. */
export function pageUrl(route: string): string {
  const base = `${window.location.origin}${import.meta.env.BASE_URL}`
  return import.meta.env.VITE_STATIC === '1' ? `${base}#${route}` : `${base.replace(/\/$/, '')}${route}`
}

export interface StoryText { title: string; text: string; analysis?: string; generatedAt: string }

function filePath(key: string): string {
  return `stories/${key}.md`
}

/** The Markdown the edit file starts from: the AI story plus a note of which AI version it corrects. */
export function editTemplate(story: StoryText): string {
  return [
    '---',
    `ai_generated_at: ${story.generatedAt}`,
    'note: ',
    '---',
    '',
    `<!-- Correction for: ${story.title}`,
    '     Edit the text below and commit. The site rebuilds in a few minutes and shows this instead of the AI version.',
    '     "note" (optional) says what you changed. Delete this file to go back to the AI story. -->',
    '',
    '## Recap',
    '',
    story.text,
    ...(story.analysis !== undefined ? ['', '## Analysis', '', story.analysis] : []),
    '',
  ].join('\n')
}

export function editUrl(info: StoryEditInfo, story: StoryText): string {
  if (info.edited) return `https://github.com/${REPO}/edit/${BRANCH}/${filePath(info.story_key)}`
  const q = new URLSearchParams({ filename: filePath(info.story_key), value: editTemplate(story), message: `Correct story: ${story.title}` })
  return `https://github.com/${REPO}/new/${BRANCH}?${q}`
}

export function revertUrl(info: StoryEditInfo): string {
  return `https://github.com/${REPO}/delete/${BRANCH}/${filePath(info.story_key)}`
}

export function flagUrl(info: StoryEditInfo, story: StoryText, page: string): string {
  const q = new URLSearchParams({
    template: 'story-flag.yml',
    title: `Story issue: ${story.title}`,
    story: info.story_key,
    page: `${page}${page.includes('?') ? '&' : '?'}editor=1`,
  })
  return `https://github.com/${REPO}/issues/new?${q}`
}

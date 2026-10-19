import { useLayoutEffect, useRef, useSyncExternalStore } from 'react'

/** Where each story on the page came from. One line per page describes them (PageSources); a story shows
 * its own badge only when it differs from that line (REVIEW_ROUND2 A8). */
export type StorySource = 'claude' | 'template' | 'edited'
export type SourceCounts = Record<StorySource, number>

const mounted = new Map<symbol, StorySource>()
const listeners = new Set<() => void>()
function subscribe(l: () => void) { listeners.add(l); return () => { listeners.delete(l) } }
function snapshot(): string {
  const c: SourceCounts = { claude: 0, template: 0, edited: 0 }
  for (const s of mounted.values()) c[s] += 1
  return `${c.claude}|${c.template}|${c.edited}`
}
function parse(key: string): SourceCounts {
  const [claude, template, edited] = key.split('|').map(Number)
  return { claude, template, edited }
}

export function asSource(s: string | undefined, edited?: boolean): StorySource {
  return edited || s === 'edited' ? 'edited' : s === 'template' ? 'template' : 'claude'
}

/** The page's main source: what most of its stories are. */
export function primarySource(c: SourceCounts): StorySource {
  return c.claude >= c.template && c.claude > 0 ? 'claude' : 'template'
}

export function usePageSources(): SourceCounts {
  return parse(useSyncExternalStore(subscribe, snapshot, () => '0|0|0'))
}

/** Registers one story; returns its own badge text, or null when the page line already describes it. */
export function useStorySource(source: StorySource): string | null {
  const id = useRef(Symbol('story'))
  useLayoutEffect(() => {
    const key = id.current
    mounted.set(key, source)
    for (const l of listeners) l()
    return () => { mounted.delete(key); for (const l of listeners) l() }
  }, [source])
  const counts = usePageSources()
  if (source === 'edited') return 'Corrected by the editor'
  if (source !== primarySource(counts)) return source === 'template' ? 'Computed from the timing data' : 'Written by Claude and fact-checked'
  return null
}

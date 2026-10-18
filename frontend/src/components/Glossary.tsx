import { useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore, type ReactNode } from 'react'
import { GLOSSARY, UNDERLINED } from '../lib/glossary'

// Which mounted <Term> is the first one for each key, in document order. Only that one is underlined,
// so a page explains each word once (REVIEW_ROUND2 A6). Terms leave the registry when they unmount,
// so the register follows route changes by itself.
const mounted = new Map<string, Set<HTMLElement>>()
const listeners = new Set<() => void>()
function notify() { for (const l of listeners) l() }
function subscribe(l: () => void) { listeners.add(l); return () => { listeners.delete(l) } }
function firstOf(k: string): HTMLElement | null {
  let first: HTMLElement | null = null
  for (const el of mounted.get(k) ?? []) {
    if (!first || first.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING) first = el
  }
  return first
}

/** A jargon word that explains itself on hover, focus or tap: underlined the first time it appears on a page. */
export function Term({ k, children }: { k: string; children?: ReactNode }) {
  const entry = GLOSSARY[k]
  const listed = !!entry && UNDERLINED.has(k)
  const [open, setOpen] = useState(false)
  const id = useId()
  const ref = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!listed || !el) return
    const set = mounted.get(k) ?? new Set()
    set.add(el)
    mounted.set(k, set)
    notify()
    return () => { set.delete(el); notify() }
  }, [k, listed])
  const first = useSyncExternalStore(subscribe, () => listed && !!ref.current && firstOf(k) === ref.current, () => false)
  useEffect(() => {
    if (!open) return
    const close = (e: Event) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', esc) }
  }, [open])
  const text = children ?? entry?.term
  if (!first) return <span ref={ref}>{text}</span>
  return (
    <span ref={ref} className="term-wrap" data-term={k} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="term" aria-describedby={open ? id : undefined} aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o) }} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
        {text}
      </button>
      {open && (
        <span role="tooltip" id={id} className="term-tip">
          <span className="font-semibold">{entry.term}.</span> {entry.def}
        </span>
      )}
    </span>
  )
}

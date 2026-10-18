import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'

const fmt = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })

/** "Data through round 17 · updated 18 Oct": how current the page is, on home, race and standings (REVIEW_ROUND2 #42). */
export function Freshness({ className = '' }: { className?: string }) {
  const meta = useFetch((s) => api.meta(s), [])
  if (!meta.data?.last_round) return null
  return (
    <p className={`label ${className}`} title={meta.data.last_event ? `Latest results: ${meta.data.last_event}` : undefined}>
      Data through round {meta.data.last_round} · updated {fmt(meta.data.generated_at)}
    </p>
  )
}

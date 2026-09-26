import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'

export function MidfieldCard({ sessionId, onSelect, onStory }: { sessionId: number; onSelect: (id: number) => void; onStory?: (id: number | null) => void }) {
  const spot = useFetch((s) => api.midfieldSpotlight(sessionId, false, s), [sessionId])
  if (spot.data && onStory) onStory(spot.data.driver_id)
  return (
    <div className="card p-4" style={{ borderLeft: '4px solid var(--spotlight)', boxShadow: '0 0 20px -12px var(--spotlight)' }}>
      <div className="text-[11px] uppercase tracking-wide mb-1 font-bold" style={{ color: 'var(--spotlight)' }}>★ Midfield spotlight</div>
      {spot.loading && <div className="muted text-sm">Looking for the best story outside the top 3…</div>}
      {spot.error && <div className="muted text-sm">{spot.error.message}</div>}
      {spot.data && (
        <>
          <button className="text-left w-full" onClick={() => onSelect(spot.data!.driver_id)}>
            <div className="font-semibold text-lg hover:underline">{spot.data.driver} <span className="muted text-sm font-normal">· {spot.data.team}</span></div>
          </button>
          <p className="text-sm mt-1">{spot.data.reason}</p>
          <p className="faint text-xs mt-2">Click the name to read their story. Also worth a look: {spot.data.runners_up.slice(0, 2).map((r) => r.driver).join(', ') || '—'}.</p>
        </>
      )}
    </div>
  )
}

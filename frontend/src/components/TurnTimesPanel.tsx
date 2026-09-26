import { api, fmtMs, type Driver } from '../api/client'
import { useFetch } from '../hooks/useFetch'

function tierColor(deltaMs: number): string {
  if (deltaMs <= -30) return 'var(--perf-purple)'
  if (deltaMs <= 60) return 'var(--perf-green)'
  if (deltaMs <= 200) return 'var(--perf-yellow)'
  return 'var(--perf-red)'
}

export function TurnTimesPanel({ sessionId, driver, accent }: { sessionId: number; driver: Driver; accent: string }) {
  const td = useFetch((s) => api.turnDeltas(sessionId, driver.id, s), [sessionId, driver.id])
  return (
    <div className="card p-4" style={{ borderTop: `4px solid ${accent}` }}>
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <h3 className="font-semibold">{driver.code ?? driver.name} <span className="muted font-normal text-sm">· turn-by-turn vs the reference lap</span></h3>
        {td.data && <span className="font-mono text-sm" style={{ color: td.data.total_lap_delta_ms <= 0 ? 'var(--perf-green)' : 'var(--perf-red)' }}>{fmtMs(td.data.total_lap_delta_ms, true)} total</span>}
      </div>
      {td.loading && <div className="muted text-sm">Comparing lap telemetry…</div>}
      {td.error && <div className="muted text-sm">{td.error.message}</div>}
      {td.data && (
        <>
          {td.data.is_reference_lap ? (
            <p className="text-sm muted">This is the reference lap itself (the fastest available lap for this event) - it's the zero point everyone else is measured against.</p>
          ) : (
            <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
              {td.data.turns.map((t) => (
                <div key={t.number} className="card px-2 py-1.5 text-center" style={{ borderTop: `3px solid ${tierColor(t.delta_ms)}` }} title={`Sector ${t.sector} · apex ${t.apex_speed_kph.toFixed(0)} km/h`}>
                  <div className="text-[10px] uppercase faint">T{t.number}</div>
                  <div className="font-mono text-sm font-semibold">{fmtMs(t.delta_ms, true)}</div>
                </div>
              ))}
            </div>
          )}
          <p className="faint text-[11px] mt-2">{td.data.note}</p>
        </>
      )}
    </div>
  )
}

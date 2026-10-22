import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, type StandingRow } from '../api/client'
import { Freshness } from '../components/Freshness'
import { StoryMeta } from '../components/StoryMeta'
import { useFetch } from '../hooks/useFetch'
import { useTitle } from '../hooks/useTitle'
import { STATUS_TEXT } from '../lib/f1'
import { teamColor } from '../lib/teamColors'
import { SpoilerGate, usePrefs } from '../state/prefs'
import { useStore } from '../state/store'

// one neutral ramp: wins brightest, podiums, then points finishes; the rest stay unfilled
function cell(pos: number | null | undefined): string {
  if (!pos) return 'rc-none'
  if (pos === 1) return 'rc-win'
  if (pos <= 3) return 'rc-podium'
  if (pos <= 10) return 'rc-points'
  return 'rc-none'
}

const fmtPts = (p: number) => (p % 1 ? p.toFixed(1) : String(p))

/** Points through the season for the top six, as SVG paths (#61: the charting library made this page 70–80 on a
 * phone). Hover or tap a round for everyone's total. */
function PointsLines({ data, top, dashed, rounds, nameOf }: { data: Record<string, number>[]; top: StandingRow[]; dashed: boolean[]; rounds: number[]; nameOf: (r: number) => string }) {
  const [at, setAt] = useState<number | null>(null)
  const W = 640, H = 300, L = 34, R = 12, T = 8, B = 22
  const max = Math.max(1, ...data.flatMap((p) => top.map((d) => p[d.driver_id] ?? 0)))
  const nice = Math.ceil(max / 100) * 100 // gridlines on whole hundreds
  const x = (i: number) => L + (i / Math.max(1, rounds.length - 1)) * (W - L - R)
  const y = (v: number) => T + (1 - v / nice) * (H - T - B)
  const pick = (e: React.PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const vx = ((e.clientX - box.left) / box.width) * W
    setAt(Math.max(0, Math.min(rounds.length - 1, Math.round(((vx - L) / (W - L - R)) * (rounds.length - 1)))))
  }
  const grid = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(nice * f))
  const point = at != null ? data[at] : undefined
  return (
    <div className="relative h-full min-h-[300px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[300px]" preserveAspectRatio="none" role="img" onPointerMove={pick} onPointerLeave={() => setAt(null)}
        aria-label={`Points after each round for ${top.map((d) => d.code).join(', ')}`}>
        {grid.map((g) => <line key={g} x1={L} x2={W - R} y1={y(g)} y2={y(g)} stroke="var(--line)" vectorEffect="non-scaling-stroke" />)}
        {at != null && <line x1={x(at)} x2={x(at)} y1={T} y2={H - B} stroke="var(--line-2)" vectorEffect="non-scaling-stroke" />}
        {top.map((d, i) => (
          <path key={d.driver_id} d={data.map((p, k) => `${k ? 'L' : 'M'}${x(k).toFixed(1)},${y(p[d.driver_id] ?? 0).toFixed(1)}`).join('')}
            fill="none" stroke={teamColor(d.team)} strokeWidth={2} strokeDasharray={dashed[i] ? '5 4' : undefined} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        ))}
      </svg>
      <div className="absolute inset-y-0 left-0 w-8 text-[11px] t3 num pointer-events-none" aria-hidden="true">
        {grid.map((g) => <span key={g} className="absolute -translate-y-1/2" style={{ top: `${(y(g) / H) * 300}px` }}>{g}</span>)}
      </div>
      <div className="relative h-4 text-[11px] t3 num pointer-events-none" aria-hidden="true">
        {rounds.map((r, k) => (k % Math.ceil(rounds.length / 12) === 0 || k === rounds.length - 1) && <span key={r} className="absolute -translate-x-1/2" style={{ left: `${(x(k) / W) * 100}%` }}>R{r}</span>)}
      </div>
      {point && at != null && (
        <div className="tip num absolute top-2 pointer-events-none" style={{ left: `min(calc(${(x(at) / W) * 100}% + 10px), calc(100% - 10rem))` }}>
          <div className="label mb-1">{nameOf(rounds[at])}</div>
          {[...top].sort((a, b) => (point[b.driver_id] ?? 0) - (point[a.driver_id] ?? 0)).map((d) => (
            <div key={d.driver_id} className="flex items-center gap-2"><span className="swatch h-3" style={{ background: teamColor(d.team) }} /><span className="w-9">{d.code}</span><span className="ml-auto">{fmtPts(point[d.driver_id] ?? 0)}</span></div>
          ))}
        </div>
      )}
    </div>
  )
}

function TitleFight({ rows, rounds, nameOf }: { rows: StandingRow[]; rounds: number[]; nameOf: (r: number) => string }) {
  const top = rows.slice(0, 6)
  const data = useMemo(() => {
    const run: Record<number, number> = {}
    return rounds.map((r) => {
      const point: Record<string, number> = { round: r }
      for (const d of top) point[d.driver_id] = run[d.driver_id] = (run[d.driver_id] ?? 0) + (d.round_points[String(r)] ?? 0)
      return point
    })
  }, [top, rounds])
  // teammates share a team colour, so the second one is dashed (legend above, values on hover)
  const seen = new Set<string>()
  const dashed = top.map((d) => { const k = d.team ?? ''; const dup = seen.has(k); seen.add(k); return dup })
  return (
    <section className="panel lg:col-span-8 flex flex-col" aria-label="Title fight">
      <div className="panel-head">
        <h2 className="h2">Title fight</h2>
        <div className="flex flex-wrap gap-x-3 gap-y-1 justify-end">
          {top.map((d, i) => (
            <span key={d.driver_id} className="label flex items-center gap-1.5">
              <svg width="14" height="2" aria-hidden="true"><line x1="0" y1="1" x2="14" y2="1" stroke={teamColor(d.team)} strokeWidth="2" strokeDasharray={dashed[i] ? '4 3' : undefined} /></svg>{d.code}
            </span>
          ))}
        </div>
      </div>
      <div className="panel-body flex-1 min-h-[300px]">
        <PointsLines data={data} top={top} dashed={dashed} rounds={rounds} nameOf={nameOf} />
      </div>
    </section>
  )
}

function Leader({ rows, rounds }: { rows: StandingRow[]; rounds: number[] }) {
  const [a, b] = rows
  if (!a) return null
  const last = rounds.at(-1)
  return (
    <section className="panel relative overflow-hidden lg:col-span-4 p-6 flex flex-col" aria-label="Championship leader">
      <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: teamColor(a.team) }} />
      <div className="kicker">Championship leader</div>
      <div className="h-feature mt-3">{a.name.split(' ').at(-1)}</div>
      <div className="t2 text-[13px] mt-1">{a.name}, {a.team}</div>
      <div className="grid grid-cols-3 gap-4 mt-auto pt-8">
        <div><div className="label">Points</div><div className="stat mt-1 num">{fmtPts(a.points)}</div></div>
        <div><div className="label">Lead</div><div className="stat mt-1 num">{b ? `+${fmtPts(a.points - b.points)}` : '–'}</div></div>
        <div><div className="label">Wins</div><div className="stat mt-1 num">{a.wins}</div></div>
      </div>
      {b && <div className="label mt-5 pt-4 border-t" style={{ borderColor: 'var(--line)' }}>Second: {b.name}, {fmtPts(b.points)} points{last ? ` after round ${last}` : ''}</div>}
    </section>
  )
}

function Story({ year, type, id, title, color }: { year: number; type: 'driver' | 'team'; id: string; title: string; color: string }) {
  const arc = useFetch((s) => api.seasonArc(year, type, id, s), [year, type, id])
  return (
    <section className="panel mb-4" aria-label={`${title} season story`}>
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: 'var(--line)' }}>
        <span className="swatch h-6 w-1" style={{ background: color }} />
        <div>
          <div className="h2">{title}</div>
          <div className="label">Season so far{arc.data ? `, through round ${arc.data.through_round}` : ''}</div>
        </div>
      </div>
      <div className="px-5 py-5">
        {arc.loading && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-4" style={{ width: `${88 - i * 14}%` }} />)}</div>}
        {arc.error && <p className="t2">{arc.error.message}</p>}
        {arc.data && (
          <>
            <p className="prose whitespace-pre-line max-w-3xl">{arc.data.arc_text}</p>
            <div className="mt-5"><StoryMeta info={arc.data} route={`/season/${year}?type=${type}&id=${encodeURIComponent(id)}`} story={{ title: `${year} season · ${title}`, text: arc.data.arc_text, generatedAt: arc.data.generated_at ?? "" }} /></div>
          </>
        )}
      </div>
    </section>
  )
}

export function SeasonPage() {
  const year = Number(useParams().year)
  const { setYear } = useStore()
  useEffect(() => { if (year) setYear(year) }, [year, setYear])
  useTitle(year ? `${year} standings` : null)
  const [search] = useSearchParams()
  const [view, setView] = useState<'drivers' | 'teams'>(search.get('type') === 'team' ? 'teams' : 'drivers')
  const [pick, setPick] = useState<{ type: 'driver' | 'team'; id: string } | null>(search.get('id') ? { type: search.get('type') === 'team' ? 'team' : 'driver', id: search.get('id')! } : null)
  const st = useFetch((s) => api.standings(year, s), [year], !!year)
  const events = useFetch((s) => api.events(year, s), [year], !!year)
  const rounds = st.data?.rounds ?? []
  // the season grid (about 400 cells) renders at low priority, in slices, after the chart and leader (#61)
  const grid = useDeferredValue(st.data)
  const nameOf = (r: number) => events.data?.find((e) => e.round === r)?.name.replace(' Grand Prix', '') ?? `Round ${r}`
  const pickedDriver: StandingRow | undefined = pick?.type === 'driver' ? st.data?.drivers.find((d) => String(d.driver_id) === pick.id) : undefined
  const { hidden } = usePrefs()
  const secret = rounds.filter((r) => hidden(r))

  return (
    <div className="wrap pt-10">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="h1">{year} standings</h1>
          <Freshness className="mt-2" />
          {rounds.length > 0 && <p className="t2 mt-1.5 text-[14px]" data-hint>Select a {view === 'drivers' ? 'driver' : 'team'} for their season story.</p>}
        </div>
        <div className="seg">
          <button aria-pressed={view === 'drivers'} onClick={() => setView('drivers')}>Drivers</button>
          <button aria-pressed={view === 'teams'} onClick={() => setView('teams')}>Constructors</button>
        </div>
      </div>

      {secret.length > 0 && <SpoilerGate className="mb-6" rounds={secret} what={`Spoiler-free mode is on: the standings include round ${secret[0]}.`} />}
      {secret.length === 0 && st.data && view === 'drivers' && st.data.drivers.length > 0 && (
        <div className="grid lg:grid-cols-12 gap-4 mb-4">
          <TitleFight rows={st.data.drivers} rounds={rounds} nameOf={nameOf} />
          <Leader rows={st.data.drivers} rounds={rounds} />
        </div>
      )}

      {pick && st.data && (
        pick.type === 'driver'
          ? pickedDriver && <Story key={`d${pick.id}`} year={year} type="driver" id={pick.id} title={pickedDriver.name} color={teamColor(pickedDriver.team)} />
          : <Story key={`t${pick.id}`} year={year} type="team" id={pick.id} title={pick.id} color={teamColor(pick.id)} />
      )}

      {st.error && <p className="t2">{st.error.message}</p>}
      {st.loading && <div className="panel skeleton h-[600px]" />}

      {secret.length === 0 && grid && view === 'drivers' && (
        <section className="panel overflow-x-auto" aria-label="Driver standings">
          <table className="tbl">
            <thead>
              <tr>
                <th className="w-10">Pos</th><th>Driver</th><th className="r">Pts</th><th className="r">Wins</th><th className="r">Pod.</th>
                {rounds.map((r) => <th key={r} className="!px-0 text-center w-8" title={nameOf(r)}>{r}</th>)}
              </tr>
            </thead>
            <tbody>
              {grid.drivers.map((d) => {
                const on = pick?.type === 'driver' && pick.id === String(d.driver_id)
                return (
                  <tr key={d.driver_id} className="clickable" aria-selected={on} onClick={() => setPick({ type: 'driver', id: String(d.driver_id) })}>
                    <td className="num t2">{d.position}</td>
                    <td>
                      <div className="flex items-center gap-2.5">
                        <span className="swatch h-4" style={{ background: teamColor(d.team) }} />
                        <span className="font-medium">{d.name}</span>
                        <span className="t3 hidden md:inline">{d.team}{d.teams.length > 1 && <span title={`Also drove for ${d.teams.filter((t) => t !== d.team).join(', ')} this season`}>, also {d.teams.filter((t) => t !== d.team).join(', ')}</span>}</span>
                      </div>
                    </td>
                    <td className="r num font-semibold">{fmtPts(d.points)}</td>
                    <td className="r num t2">{d.wins || ''}</td>
                    <td className="r num t2">{d.podiums || ''}</td>
                    {rounds.map((r) => {
                      const res = d.results[String(r)]
                      const p = res?.position ?? null
                      const code = res && !p ? res.status : null
                      const elsewhere = res?.team && res.team !== d.team
                      const what = !res ? 'did not take part' : p ? `P${p}${code === 'DNF' ? ' (retired, classified)' : ''}` : res.status ? STATUS_TEXT[res.status] : 'no result'
                      // one element per cell, styled by class: 400 of these made the page's longest task (#61)
                      return (
                        <td key={r} className={`rc ${cell(p)}${code ? ' rc-code' : ''}`} title={`${nameOf(r)}: ${what}${elsewhere ? ` · for ${res!.team}` : ''}`}
                          style={elsewhere ? { boxShadow: `inset 0 -2px 0 ${teamColor(res!.team)}` } : undefined}>
                          {p ?? code ?? ''}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      )}

      {secret.length === 0 && st.data && view === 'teams' && (
        <section className="panel" aria-label="Constructor standings">
          <table className="tbl">
            <thead><tr><th className="w-10">Pos</th><th>Team</th><th className="w-1/2" /><th className="r">Pts</th></tr></thead>
            <tbody>
              {st.data.teams.map((t) => {
                const max = st.data!.teams[0]?.points || 1
                const on = pick?.type === 'team' && pick.id === t.team
                return (
                  <tr key={t.team} className="clickable" aria-selected={on} onClick={() => setPick({ type: 'team', id: t.team })}>
                    <td className="num t2">{t.position}</td>
                    <td><div className="flex items-center gap-2.5"><span className="swatch h-4" style={{ background: teamColor(t.team) }} /><span className="font-medium">{t.team}</span></div></td>
                    <td><div className="h-[8px]" style={{ width: `${(t.points / max) * 100}%`, background: teamColor(t.team), opacity: 0.8 }} /></td>
                    <td className="r num font-semibold">{t.points % 1 ? t.points.toFixed(1) : t.points}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

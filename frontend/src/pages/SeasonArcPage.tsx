import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorNote, LoadingNote, RecapAndAnalysis, StoryFooter } from '../components/NarrativePanel'
import { useFetch } from '../hooks/useFetch'

export function SeasonArcPage() {
  const year = Number(useParams().year)
  const drivers = useFetch((s) => api.drivers(s), [])
  const [search] = useSearchParams()  // deep link: ?type=team&id=Alpine
  const [subjectType, setSubjectType] = useState<'driver' | 'team'>(search.get('type') === 'team' ? 'team' : 'driver')
  const [subjectId, setSubjectId] = useState<string>(search.get('id') ?? '')
  const arc = useFetch((s) => api.seasonArc(year, subjectType, subjectId, s), [year, subjectType, subjectId], subjectId !== '')
  const teams = [...new Set((drivers.data ?? []).map((d) => d.team).filter(Boolean))].sort() as string[]
  const named = (drivers.data ?? []).filter((d) => !d.driver_ref.startsWith('driver_')).sort((a, b) => a.name.localeCompare(b.name))
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      <Link to="/" className="text-sm muted hover:underline">← All races</Link>
      <h1 className="display text-2xl sm:text-3xl">{year} season · story so far</h1>
      <div className="flex flex-wrap gap-2 items-center">
        <button className="btn" aria-pressed={subjectType === 'driver'} onClick={() => { setSubjectType('driver'); setSubjectId('') }}>Driver</button>
        <button className="btn" aria-pressed={subjectType === 'team'} onClick={() => { setSubjectType('team'); setSubjectId('') }}>Team</button>
        <select className="btn" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
          <option value="">Choose…</option>
          {subjectType === 'driver' ? named.map((d) => <option key={d.id} value={String(d.id)}>{d.name} · {d.team}</option>) : teams.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      {arc.loading && <LoadingNote what="the season arc" />}
      {arc.error && <ErrorNote error={arc.error} />}
      {arc.data && (
        <div className="card p-4">
          <RecapAndAnalysis
            recap={arc.data.arc_text}
            footer={
              <StoryFooter
                info={arc.data}
                route={`/season/${year}?type=${subjectType}&id=${encodeURIComponent(subjectId)}`}
                story={{ title: `${year} season · ${subjectType === 'team' ? subjectId : (named.find((d) => String(d.id) === subjectId)?.name ?? subjectId)}`, text: arc.data.arc_text, generatedAt: arc.data.generated_at }}
                meta={`through round ${arc.data.through_round}`}
              />
            }
          />
        </div>
      )}
    </div>
  )
}

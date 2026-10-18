/**
 * Typed client for the F1 tracker backend. Base URL: VITE_API_BASE (default: same origin / dev proxy).
 *
 * Static mode (VITE_STATIC=1, the GitHub Pages build): every call reads a pre-exported JSON file from
 * `<base>/data/...` instead (see f1tracker/export.py). Nothing is generated on request there - stories
 * were written by the pipeline when the data was processed.
 */
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
export const STATIC = import.meta.env.VITE_STATIC === '1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const NOT_READY = 'Not available yet - it appears once this session has been processed.'
const staticCache = new Map<string, Promise<unknown>>()

/** `live`: API path. `file`: static JSON path (no extension). `missing`: message when the file doesn't exist. */
async function get<T>(live: string, signal?: AbortSignal, file?: string, missing = NOT_READY): Promise<T> {
  if (STATIC) {
    const url = `${import.meta.env.BASE_URL}data/${file ?? live.replace(/^\//, '')}.json`
    let p = staticCache.get(url) as Promise<T> | undefined
    if (!p) {
      // not tied to one caller's AbortSignal: the result is shared through the cache
      p = fetch(url).then(async (res) => {
        if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) throw new ApiError(404, missing)
        return (await res.json()) as T
      })
      p.catch(() => staticCache.delete(url))
      staticCache.set(url, p)
    }
    if (signal?.aborted) throw new DOMException('aborted', 'AbortError')
    return p
  }
  const res = await fetch(`${BASE}${live}`, { signal })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export type SessionType = 'FP1' | 'FP2' | 'FP3' | 'SQ' | 'S' | 'Q' | 'R'

export interface Season { id: number; year: number }
export interface Event {
  id: number; season_id: number; round: number; name: string; circuit_name: string | null; country: string | null
  event_date: string | null; has_sprint: boolean; openf1_meeting_key: number | null; season_year: number
  lat: number | null; lon: number | null
  winner?: Driver | null; podium?: Driver[]; completed?: boolean
  outline_preview?: { points: [number, number][] } | null
}
export type RaceStatus = 'FIN' | 'LAP' | 'DNF' | 'NC' | 'DNS' | 'DSQ'
export interface RoundResult { position: number | null; status: RaceStatus | null; team: string | null }
export interface StandingRow {
  position: number; driver_id: number; name: string; code: string | null; team: string | null; teams: string[]
  points: number; wins: number; podiums: number; results: Record<string, RoundResult>; round_points: Record<string, number>
}
export interface TeamStanding { position: number; team: string; constructor_id: string | null; points: number }
export interface Standings { year: number; rounds: number[]; drivers: StandingRow[]; teams: TeamStanding[] }
export interface SessionRow {
  id: number; event_id: number; session_type: SessionType; start_time: string | null; end_time: string | null
  status: 'upcoming' | 'live' | 'completed'; openf1_session_key: number | null
  ingestion: { results: boolean; details: boolean; transforms: boolean }
}
/** A driver as entered for one event: team and car number are that weekend's. */
export interface Driver {
  id: number; driver_ref: string; name: string; code: string | null; team: string | null; number: number | null
  stand_in?: boolean; usual_team?: string | null; practice_only?: boolean
}
export interface GeoBBox { south: number; west: number; north: number; east: number }
export interface Turn { number: number; index: number; distance_m: number; apex_speed_kph: number }
export interface TrackOutline {
  event_id: number; points: [number, number][]; sector_1_end_index: number; sector_2_end_index: number
  drs_zones: [number, number][]; drs_zone_source: 'telemetry' | 'estimated_throttle' | 'none'
  geo_points: [number, number][] | null; geo_bbox: GeoBBox | null
  turns: Turn[]
  orientation?: 'f1' | 'estimated'
  source: { session_id: number; driver_id: number; lap_number: number }; note: string
}
export interface TurnDelta { number: number; sector: 1 | 2 | 3; distance_m: number; from_m?: number; to_m?: number; apex_speed_kph: number; delta_ms: number }
/** Corners + unattributed_ms = total_lap_delta_ms = lap_time_ms - reference.lap_time_ms. */
export interface TurnDeltas {
  version?: number; session_id: number; driver_id: number; lap_number: number; lap_time_ms?: number; is_reference_lap: boolean
  reference: { session_id: number; driver_id: number; lap_number: number; lap_time_ms?: number }
  turns: TurnDelta[]; total_lap_delta_ms: number; unattributed_ms?: number; note: string
}
export interface HeadlinePractice { session_id: number; driver_id: number; fastest_lap_ms: number | null; gap_to_fastest_ms: number | null; rank: number | null }
/** gap_to_pole_ms is measured inside gap_segment (pole for Q3 runners, the fastest Q2 time for Q2 exits...). */
export interface HeadlineQualifying {
  session_id: number; driver_id: number; position: number | null; gap_to_pole_ms: number | null; gap_segment: 'Q1' | 'Q2' | 'Q3' | null
  eliminated_in: string | null; status_code: 'OK' | 'NO_TIME' | 'DNS' | 'DSQ' | null; q1_ms: number | null; q2_ms: number | null; q3_ms: number | null
}
export interface HeadlineRace {
  session_id: number; driver_id: number; finish_position: number | null; grid_position: number | null; positions_gained: number | null
  points: number; pit_stop_count: number; status: string | null; status_code: RaceStatus; classification_order: number | null
  laps_completed: number | null; laps_down: number | null
}
export interface RaceCounts { classified: number; dnf: number; dns: number; dsq: number }
export interface Headline {
  session: SessionRow; summary: string | null; drivers: Record<string, Driver>
  practice?: HeadlinePractice[]; qualifying?: HeadlineQualifying[]; race?: HeadlineRace[]; counts?: RaceCounts
}
export interface SectorDelta { session_id: number; driver_id: number; lap_number: number; sector: 1 | 2 | 3; driver_sector_ms: number | null; session_best_sector_ms: number | null; delta_ms: number | null }
export interface PositionByLap { session_id: number; driver_id: number; lap_number: number; position: number | null }
export interface StintRow { session_id: number; driver_id: number; stint_number: number; compound: string | null; lap_start: number | null; lap_end: number | null }
export interface PitStopRow { id: number; session_id: number; driver_id: number; lap_number: number; duration_ms: number | null; lane_duration_ms: number | null }
export interface Detail {
  long_run_pace: { driver_id: number; compound: string; avg_lap_time_ms: number; lap_count: number }[]
  qualifying_segments: { driver_id: number; segment: string; best_lap_ms: number; gap_to_segment_leader_ms: number }[]
  stint_timeline: StintRow[]
  degradation: { driver_id: number; stint_number: number; lap_number_in_stint: number; lap_time_ms: number }[]
  position_by_lap: PositionByLap[]
  sector_deltas: SectorDelta[]
  pit_stops: PitStopRow[]
}
/** Every stored story carries where its human-edit file lives and whether that edit is in effect. */
export interface StoryEditInfo {
  story_key: string; edited: boolean; edit_note?: string | null; edit_stale?: boolean
}
/** A driver-session story. narrative_text = the full story, strategy_analysis_text = the analysis. */
export interface Narrative extends StoryEditInfo {
  session_id: number; driver_id: number; session_type: SessionType; narrative_text: string; strategy_analysis_text: string
  generated_at: string | null; model_used: string
  headline?: string | null; summary?: string | null; key_numbers?: { label: string; value: string }[]; glossary_terms?: string[]
  source?: 'claude' | 'template' | 'edited'; replaced_because?: string
}
export interface WeekendArc extends StoryEditInfo { event_id: number; driver_id: number; arc_text: string; generated_at: string | null; model_used: string; source?: string }
export interface SeasonArc extends StoryEditInfo { season_id: number; subject_type: 'driver' | 'team'; subject_id: string; through_round: number; arc_text: string; generated_at: string | null; model_used: string; source?: string }
export interface ComparisonNarrative extends StoryEditInfo { driver_a_id: number; driver_b_id: number; comparison_text: string; generated_at: string | null; model_used: string; source?: string }
export interface PivotalMoment {
  id: number; session_id: number; lap_number: number | null; end_lap: number | null; driver_id: number | null; related_driver_id: number | null
  moment_type: string; magnitude_score: number; description: string; headline: string | null; detail: string | null
}
export interface RaceControlEvent { lap_number: number | null; time: string; kind: string; driver_ids: number[]; turn: number | null; reason: string | null; outcome: string | null; text: string }
export interface IncidentCase { id: string; driver_ids: number[]; turn: number | null; reason: string | null; opened_lap: number | null; decided_lap: number | null; outcome: string | null; after_race: boolean }
export interface NeutralPeriod { kind: 'SC' | 'VSC' | 'RED'; start_lap: number | null; end_lap: number | null }
export interface RaceControl { periods: NeutralPeriod[]; cases: IncidentCase[]; events: RaceControlEvent[] }
export interface ChartAnnotation { lap_number: number | null; end_lap?: number | null; driver_id: number | null; label: string; moment_type: string; description: string; magnitude_score: number }
export interface MidfieldStory {
  driver_id: number; driver: string; team: string | null; score: number; story_types: string[]; reason: string; rival_id: number | null
  runners_up: { driver_id: number; driver: string; team?: string | null; score: number; reason: string; story_types?: string[] }[]; narrative?: Narrative
}
export interface CompareDriver {
  id: number; name: string; team: string | null; position_by_lap: { lap: number; position: number }[]
  stints: { stint: number; compound: string | null; lap_start: number | null; lap_end: number | null }[]
}
export interface Comparison {
  session_id: number; session_type: SessionType; driver_a: CompareDriver; driver_b: CompareDriver
  gap_over_time: { lap: number; gap_ms: number; gap_formatted: string }[]
  narrative?: ComparisonNarrative
}

export interface SiteMeta { season_year: number | null; last_round: number | null; last_event: string | null; generated_at: string }

export const api = {
  meta: (s?: AbortSignal) => get<SiteMeta>('/meta', s),
  seasons: (s?: AbortSignal) => get<Season[]>('/seasons', s),
  events: (year: number, s?: AbortSignal) => get<Event[]>(`/seasons/${year}/events`, s),
  standings: (year: number, s?: AbortSignal) => get<Standings>(`/seasons/${year}/standings`, s, undefined, 'No results yet this season.'),
  sessions: (eventId: number, s?: AbortSignal) => get<SessionRow[]>(`/events/${eventId}/sessions`, s),
  drivers: (s?: AbortSignal) => get<Driver[]>('/drivers', s),
  trackOutline: (eventId: number, s?: AbortSignal) => get<TrackOutline>(`/events/${eventId}/track-outline`, s),
  headline: (sessionId: number, s?: AbortSignal) => get<Headline>(`/sessions/${sessionId}/headline`, s),
  detail: (sessionId: number, driverId?: number, s?: AbortSignal) =>
    STATIC ? staticDetail(sessionId, s) : get<Detail>(`/sessions/${sessionId}/detail${driverId ? `?driver_id=${driverId}` : ''}`, s),
  narrative: (sessionId: number, driverId: number, s?: AbortSignal) =>
    get<Narrative>(`/sessions/${sessionId}/drivers/${driverId}/narrative`, s, undefined, STORY_NOT_WRITTEN),
  weekendArc: (eventId: number, driverId: number, s?: AbortSignal) =>
    get<WeekendArc>(`/events/${eventId}/drivers/${driverId}/weekend-arc`, s, undefined, STORY_NOT_WRITTEN),
  seasonArc: (season: number, subjectType: 'driver' | 'team', subjectId: string, s?: AbortSignal) =>
    get<SeasonArc>(
      `/seasons/${season}/arc?subject_type=${subjectType}&subject_id=${encodeURIComponent(subjectId)}`, s,
      `seasons/${season}/arc/${subjectType}/${subjectType === 'team' ? slug(subjectId) : subjectId}`, STORY_NOT_WRITTEN,
    ),
  pivotalMoments: (sessionId: number, s?: AbortSignal) => get<PivotalMoment[]>(`/sessions/${sessionId}/pivotal-moments`, s),
  chartAnnotations: (sessionId: number, s?: AbortSignal) => get<ChartAnnotation[]>(`/sessions/${sessionId}/chart-annotations`, s),
  raceControl: (sessionId: number, s?: AbortSignal) => get<RaceControl>(`/sessions/${sessionId}/race-control`, s),
  midfieldSpotlight: (sessionId: number, generate: boolean, s?: AbortSignal) =>
    get<MidfieldStory | null>(`/sessions/${sessionId}/midfield-spotlight?generate=${generate}`, s, `sessions/${sessionId}/midfield-spotlight`, 'No midfield story stood out in this session.'),
  compare: (sessionId: number, a: number, b: number, generate: boolean, s?: AbortSignal) =>
    STATIC ? staticCompare(sessionId, a, b, s) : get<Comparison>(`/sessions/${sessionId}/compare?driver_a=${a}&driver_b=${b}&generate=${generate}`, s),
  /** Static site: the drivers with a turn-by-turn breakdown in this session. Live API: null (computed on request). */
  turnDeltaDrivers: async (sessionId: number, s?: AbortSignal): Promise<number[] | null> =>
    STATIC ? (await get<{ drivers: number[] }>('', s, `sessions/${sessionId}/turn-deltas`)).drivers : null,
  turnDeltas: async (sessionId: number, driverId: number, s?: AbortSignal) => {
    // ask the index first: a breakdown that isn't exported would be a 404 in the console (REVIEW_ROUND2 #48)
    const have = await api.turnDeltaDrivers(sessionId, s)
    if (have && !have.includes(driverId)) throw new ApiError(404, TURNS_MISSING)
    return get<TurnDeltas>(`/sessions/${sessionId}/drivers/${driverId}/turn-deltas`, s, undefined, TURNS_MISSING)
  },
}

const TURNS_MISSING = 'Turn-by-turn times aren\'t available for this driver in this session.'
const STORY_NOT_WRITTEN = 'This story hasn\'t been written yet - stories are generated automatically after each session is processed.'

/** 'Red Bull Racing' -> 'red-bull-racing'. Mirrors f1tracker.narratives.edits.slug. */
export function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

/** Static mode: the detail view assembled from the small per-view files the exporter writes. */
async function staticDetail(sessionId: number, s?: AbortSignal): Promise<Detail> {
  // positions are exported for races and sprints only; asking for them elsewhere is a 404 in the console
  const { session } = await get<Headline>(`/sessions/${sessionId}/headline`, s)
  const raceLike = session.session_type === 'R' || session.session_type === 'S'
  const [pos, stints, sectors, pace] = await Promise.all([
    raceLike ? get<{ position_by_lap: PositionByLap[] }>('', s, `sessions/${sessionId}/positions`) : Promise.resolve({ position_by_lap: [] as PositionByLap[] }),
    get<{ stint_timeline: StintRow[]; pit_stops: PitStopRow[] }>('', s, `sessions/${sessionId}/stints`),
    get<{ best: { driver_id: number; sector: 1 | 2 | 3; best_ms: number }[] }>('', s, `sessions/${sessionId}/sectors`),
    get<{ long_run_pace: Detail['long_run_pace'] }>('', s, `sessions/${sessionId}/pace`),
  ])
  const sessionBest = new Map<number, number>()
  for (const b of sectors.best) sessionBest.set(b.sector, Math.min(sessionBest.get(b.sector) ?? Infinity, b.best_ms))
  return {
    long_run_pace: pace.long_run_pace,
    qualifying_segments: [],
    stint_timeline: stints.stint_timeline,
    degradation: [],
    position_by_lap: pos.position_by_lap,
    // each driver's best per sector is all the site draws from the sector table
    sector_deltas: sectors.best.map((b) => ({ session_id: sessionId, driver_id: b.driver_id, lap_number: 0, sector: b.sector, driver_sector_ms: b.best_ms, session_best_sector_ms: sessionBest.get(b.sector)!, delta_ms: b.best_ms - sessionBest.get(b.sector)! })),
    pit_stops: stints.pit_stops,
  }
}

/** Static mode: the API's /compare response rebuilt from exported per-session files (any pair works). */
async function staticCompare(sessionId: number, a: number, b: number, s?: AbortSignal): Promise<Comparison> {
  const [headline, detail, laps, stories] = await Promise.all([
    get<Headline>(`/sessions/${sessionId}/headline`, s),
    staticDetail(sessionId, s),
    get<Record<string, [number, number][]>>(`/sessions/${sessionId}/lap-times`, s),
    get<Record<string, ComparisonNarrative>>(`/sessions/${sessionId}/comparisons`, s),
  ])
  const side = (id: number): CompareDriver => {
    const d = headline.drivers[String(id)]
    return {
      id, name: d?.name ?? `Driver ${id}`, team: d?.team ?? null,
      position_by_lap: detail.position_by_lap.filter((r) => r.driver_id === id && r.position !== null).map((r) => ({ lap: r.lap_number, position: r.position! })),
      stints: detail.stint_timeline.filter((r) => r.driver_id === id).map((r) => ({ stint: r.stint_number, compound: r.compound, lap_start: r.lap_start, lap_end: r.lap_end })),
    }
  }
  const ta = new Map(laps[String(a)] ?? []), tb = new Map(laps[String(b)] ?? [])
  let cum = 0
  const gap_over_time = [...ta.keys()].filter((lap) => tb.has(lap)).sort((x, y) => x - y).map((lap) => {
    cum += ta.get(lap)! - tb.get(lap)!
    return { lap, gap_ms: cum, gap_formatted: `${fmtMs(cum, true)}s` }
  })
  const narrative = stories[`${Math.min(a, b)}-${Math.max(a, b)}`]
  return { session_id: sessionId, session_type: headline.session.session_type, driver_a: side(a), driver_b: side(b), gap_over_time, narrative }
}

export function fmtMs(ms: number | null | undefined, signed = false): string {
  if (ms === null || ms === undefined) return '–'
  const r = Math.round(ms) // turn deltas are fractional ms (e.g. 330.8)
  const sign = r < 0 ? '-' : signed ? '+' : ''
  const abs = Math.abs(r)
  const m = Math.floor(abs / 60000)
  const s = Math.floor((abs % 60000) / 1000)
  const f = abs % 1000
  return m > 0 ? `${sign}${m}:${String(s).padStart(2, '0')}.${String(f).padStart(3, '0')}` : `${sign}${s}.${String(f).padStart(3, '0')}`
}

export const SESSION_LABEL: Record<SessionType, string> = { FP1: 'FP1', FP2: 'FP2', FP3: 'FP3', SQ: 'Sprint Quali', S: 'Sprint', Q: 'Qualifying', R: 'Race' }

export const eventApi = { get: (eventId: number, s?: AbortSignal) => get<Event>(`/events/${eventId}`, s) }

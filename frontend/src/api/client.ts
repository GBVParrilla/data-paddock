/** Typed client for the F1 tracker backend. Base URL: VITE_API_BASE (default: same origin / dev proxy). */
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal })
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
}
export interface SessionRow {
  id: number; event_id: number; session_type: SessionType; start_time: string | null; end_time: string | null
  status: 'upcoming' | 'live' | 'completed'; openf1_session_key: number | null
  ingestion: { results: boolean; details: boolean; transforms: boolean }
}
export interface Driver { id: number; driver_ref: string; name: string; code: string | null; team: string | null; number: number | null }
export interface GeoBBox { south: number; west: number; north: number; east: number }
export interface Turn { number: number; index: number; distance_m: number; apex_speed_kph: number }
export interface TrackOutline {
  event_id: number; points: [number, number][]; sector_1_end_index: number; sector_2_end_index: number
  drs_zones: [number, number][]; drs_zone_source: 'telemetry' | 'estimated_throttle' | 'none'
  geo_points: [number, number][] | null; geo_bbox: GeoBBox | null
  turns: Turn[]
  source: { session_id: number; driver_id: number; lap_number: number }; note: string
}
export interface TurnDelta { number: number; sector: 1 | 2 | 3; distance_m: number; apex_speed_kph: number; delta_ms: number }
export interface TurnDeltas {
  session_id: number; driver_id: number; lap_number: number; is_reference_lap: boolean
  reference: { session_id: number; driver_id: number; lap_number: number }
  turns: TurnDelta[]; total_lap_delta_ms: number; note: string
}
export interface HeadlinePractice { session_id: number; driver_id: number; fastest_lap_ms: number | null; gap_to_fastest_ms: number | null; rank: number | null }
export interface HeadlineQualifying { session_id: number; driver_id: number; position: number | null; gap_to_pole_ms: number | null; eliminated_in: string | null }
export interface HeadlineRace {
  session_id: number; driver_id: number; finish_position: number | null; grid_position: number | null; positions_gained: number | null
  points: number; pit_stop_count: number; status: string | null
}
export interface Headline {
  session: SessionRow; summary: string | null; drivers: Record<string, Driver>
  practice?: HeadlinePractice[]; qualifying?: HeadlineQualifying[]; race?: HeadlineRace[]
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
export interface Narrative {
  id: number; session_id: number; driver_id: number; session_type: SessionType; narrative_text: string; strategy_analysis_text: string
  generated_at: string; model_used: string; input_hash: string
}
export interface WeekendArc { id: number; event_id: number; driver_id: number; arc_text: string; generated_at: string; model_used: string }
export interface SeasonArc { id: number; season_id: number; subject_type: 'driver' | 'team'; subject_id: string; through_round: number; arc_text: string; generated_at: string; model_used: string }
export interface PivotalMoment { id: number; session_id: number; lap_number: number | null; driver_id: number | null; moment_type: string; magnitude_score: number; description: string }
export interface ChartAnnotation { lap_number: number | null; driver_id: number | null; label: string; moment_type: string; description: string; magnitude_score: number }
export interface MidfieldStory {
  driver_id: number; driver: string; team: string | null; score: number; story_types: string[]; reason: string; rival_id: number | null
  runners_up: { driver_id: number; driver: string; score: number; reason: string }[]; narrative?: Narrative
}
export interface CompareDriver {
  id: number; name: string; team: string | null; position_by_lap: { lap: number; position: number }[]
  stints: { stint: number; compound: string | null; lap_start: number | null; lap_end: number | null }[]
}
export interface Comparison {
  session_id: number; session_type: SessionType; driver_a: CompareDriver; driver_b: CompareDriver
  gap_over_time: { lap: number; gap_ms: number; gap_formatted: string }[]
  narrative?: { comparison_text: string; generated_at: string; model_used: string }
}

export const api = {
  seasons: (s?: AbortSignal) => get<Season[]>('/seasons', s),
  events: (year: number, s?: AbortSignal) => get<Event[]>(`/seasons/${year}/events`, s),
  sessions: (eventId: number, s?: AbortSignal) => get<SessionRow[]>(`/events/${eventId}/sessions`, s),
  drivers: (s?: AbortSignal) => get<Driver[]>('/drivers', s),
  trackOutline: (eventId: number, s?: AbortSignal) => get<TrackOutline>(`/events/${eventId}/track-outline`, s),
  headline: (sessionId: number, s?: AbortSignal) => get<Headline>(`/sessions/${sessionId}/headline`, s),
  detail: (sessionId: number, driverId?: number, s?: AbortSignal) => get<Detail>(`/sessions/${sessionId}/detail${driverId ? `?driver_id=${driverId}` : ''}`, s),
  narrative: (sessionId: number, driverId: number, s?: AbortSignal) => get<Narrative>(`/sessions/${sessionId}/drivers/${driverId}/narrative`, s),
  weekendArc: (eventId: number, driverId: number, s?: AbortSignal) => get<WeekendArc>(`/events/${eventId}/drivers/${driverId}/weekend-arc`, s),
  seasonArc: (season: number, subjectType: 'driver' | 'team', subjectId: string, s?: AbortSignal) =>
    get<SeasonArc>(`/seasons/${season}/arc?subject_type=${subjectType}&subject_id=${encodeURIComponent(subjectId)}`, s),
  pivotalMoments: (sessionId: number, s?: AbortSignal) => get<PivotalMoment[]>(`/sessions/${sessionId}/pivotal-moments`, s),
  chartAnnotations: (sessionId: number, s?: AbortSignal) => get<ChartAnnotation[]>(`/sessions/${sessionId}/chart-annotations`, s),
  midfieldSpotlight: (sessionId: number, generate: boolean, s?: AbortSignal) => get<MidfieldStory>(`/sessions/${sessionId}/midfield-spotlight?generate=${generate}`, s),
  compare: (sessionId: number, a: number, b: number, generate: boolean, s?: AbortSignal) =>
    get<Comparison>(`/sessions/${sessionId}/compare?driver_a=${a}&driver_b=${b}&generate=${generate}`, s),
  turnDeltas: (sessionId: number, driverId: number, s?: AbortSignal) => get<TurnDeltas>(`/sessions/${sessionId}/drivers/${driverId}/turn-deltas`, s),
}

export function fmtMs(ms: number | null | undefined, signed = false): string {
  if (ms === null || ms === undefined) return '–'
  const sign = ms < 0 ? '-' : signed ? '+' : ''
  const abs = Math.abs(ms)
  const m = Math.floor(abs / 60000)
  const s = Math.floor((abs % 60000) / 1000)
  const f = abs % 1000
  return m > 0 ? `${sign}${m}:${String(s).padStart(2, '0')}.${String(f).padStart(3, '0')}` : `${sign}${s}.${String(f).padStart(3, '0')}`
}

export const SESSION_LABEL: Record<SessionType, string> = { FP1: 'FP1', FP2: 'FP2', FP3: 'FP3', SQ: 'Sprint Quali', S: 'Sprint', Q: 'Qualifying', R: 'Race' }

export const eventApi = { get: (eventId: number, s?: AbortSignal) => get<Event>(`/events/${eventId}`, s) }

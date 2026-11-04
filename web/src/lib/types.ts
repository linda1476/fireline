// TS mirror of server/models.py (wire format = model_dump(mode="json")). Field names are final.

export type Tag = "MAYDAY" | "DANGER" | "VICTIM_FOUND" | "HELP_NEEDED" | "ROUTINE"
export const TAGS: Tag[] = ["MAYDAY", "DANGER", "VICTIM_FOUND", "HELP_NEEDED", "ROUTINE"]
export const TAG_PRIORITY: Record<Tag, number> = { MAYDAY: 0, DANGER: 1, VICTIM_FOUND: 2, HELP_NEEDED: 3, ROUTINE: 9 }

export type DistressWhat =
  | "TRAPPED" | "FALL" | "INJURY" | "MISSING" | "COLLAPSE" | "GAS" | "LOW_AIR" | "LOST" | "OTHER" | "UNKNOWN"
export const DISTRESS_WHAT_KO: Record<DistressWhat, string> = {
  TRAPPED: "대원고립", FALL: "대원추락", INJURY: "대원부상", MISSING: "대원실종",
  COLLAPSE: "붕괴위험", GAS: "가스누출", LOW_AIR: "공기부족", LOST: "퇴로상실",
  OTHER: "기타", UNKNOWN: "미상",
}
export type VictimState = "REPORTED" | "FOUND" | "EXTRACTING" | "UNKNOWN"
export type StatusChange = "ENTERING" | "EXITING" | "LOW_AIR" | "TRAPPED" | "OK" | "NONE"
export type Strategy = "OFFENSIVE" | "DEFENSIVE" | "NONE"
export type Channel = "CMD" | "TAC" | "PTT"
export type UnitStatus = "IN" | "OUT" | "TRAPPED" | "LOW_AIR" | "OK" | "UNKNOWN"
export type UnitRole = "IC" | "CREW" | "RIT" | "EXTERIOR" | "DISPATCH"
export type ZoneKind = "indoor" | "outdoor"
export type SearchState = "none" | "primary" | "cross" | "searched"
export type CardKind = "MAYDAY" | "DANGER" | "VICTIM_FOUND" | "HELP_NEEDED" | "RULE"
export type CardState = "open" | "escalated" | "acked" | "resolved"
export type ProposalKind = "RADIO_SILENCE" | "RIT_DEPLOY" | "WITHDRAW" | "CONFIRM_STRATEGY" | "ASSIGN"
export type ProposalState = "pending" | "approved" | "edited" | "rejected"
export type BriefDecision = "push" | "hold"
export type BriefPriority = "P0" | "P1" | "P2"
export type BriefSource = "agent" | "router" | "rule"
export type TraceKind = "reasoning" | "tool_call" | "checker" | "delivery" | "fallback" | "wake"
export type Mode = "LIVE" | "REPLAY"
export type Lang = "ko" | "en"
export type CrewButton = "EVACUATE" | "VICTIM_HERE" | "SEARCH_DONE" | "NEED_HELP"
export const CREW_BUTTON_KO: Record<CrewButton, string> = {
  EVACUATE: "긴급탈출", VICTIM_HERE: "구조대상자 여기", SEARCH_DONE: "검색완료", NEED_HELP: "지원요청",
}

export interface Location { floor: number | null; zone_hint: string | null; raw: string | null }
export interface Distress {
  who: string | null; what: DistressWhat; where_raw: string | null; needs: string | null; air: string | null
}
export interface Victims { count: number | null; where_raw: string | null; state: VictimState }
export interface Triage {
  tag: Tag
  speaker_unit: string | null
  addressee: string | null
  location: Location
  distress: Distress | null
  victims: Victims | null
  hazard_terms: string[]
  status_change: StatusChange
  strategy_declared: Strategy
  needs_ack: boolean
  confidence: number
  asr_uncertain: boolean
  uncertain_reason: string | null
  evidence_span: string
  crew_brief: string | null
}

export interface Unit {
  id: string
  callsign: string
  name: string | null
  crew: number
  channel: Channel
  role: UnitRole
  lang: Lang
  aliases: string[]
  assignment: string | null
  zone_id: string | null
  status: UnitStatus
  interior: boolean
  last_heard_t: number | null
  unanswered_pings: number
  heard_count: number
  total_count: number
  label_en: string | null
}

export interface HazardNote { event_id: string; text: string; t: number }
export interface VictimReport { event_id: string; count: number | null; state: VictimState; text: string; t: number }

export interface Zone {
  id: string
  floor: number | null
  label_ko: string
  label_en: string
  kind: ZoneKind
  parent: string | null
  polygon: number[][]
  aliases: string[]
  hazards: HazardNote[]
  victim_reports: VictimReport[]
  search_state: SearchState
}

export interface Transmission {
  id: string
  channel: Channel
  turn_id: string | null
  unit_id: string | null
  line_id: string | null
  t_keyup: number
  t_final: number | null
  /** end of the clip (key-up + clip duration); backend adds it, older runs lack it */
  t_end?: number | null
  text_partial: string
  text_final: string | null
  audio_url: string | null
  source: "replay" | "live" | "ptt"
  lang: Lang
}

export interface Latency {
  asr_ms: number
  triage_ms: number
  total_ms: number
  /** ms after the end of the transmission (total minus the clip's own duration) */
  after_speech_ms?: number | null
}

export interface Event {
  id: string
  transmission_id: string
  t: number
  channel: Channel
  text: string
  triage: Triage
  speaker_unit_snapped: string | null
  zone_id_snapped: string | null
  latency: Latency
  evidence_verified: boolean
  source: "replay" | "live" | "ptt" | "button"
}

export interface Card {
  id: string
  kind: CardKind
  title: string
  title_en: string | null
  event_ids: string[]
  rule_id: string | null
  priority: number
  state: CardState
  unit_id: string | null
  zone_id: string | null
  fields: Record<string, string | null>
  missing_fields: string[]
  evidence_span: string
  channel: Channel | null
  created_t: number
  /** key-up time of the first event (Event.t); created_t is when the card became visible */
  event_t?: number | null
  acked_t: number | null
  resolved_t: number | null
  escalation_level: number
  latency_ms: number
  /** ms from end of transmission → card (backend adds it; fallback computed client-side) */
  latency_after_speech_ms?: number | null
  note: string | null
}

export interface Proposal {
  id: string
  card_id: string | null
  kind: ProposalKind
  units: string[]
  text: string
  rationale: string
  state: ProposalState
  evidence_event_id: string | null
  created_t: number
  decided_t: number | null
  source: BriefSource
}

export interface Brief {
  id: string
  unit_id: string
  decision: BriefDecision
  text: string
  priority: BriefPriority
  reason: string
  evidence_event_id: string | null
  created_t: number
  spoken_t: number | null
  source: BriefSource
  lang: Lang
}

export interface TraceEntry {
  id: string
  t: number
  wake_id: string
  wake_reason: string
  kind: TraceKind
  // tool_call: {tool, args, call_id}; checker: {tool, call_id, ok, error}; delivery: {brief_id, unit_id, decision}
  // reasoning: {summary}; fallback: {reason}; wake: {snapshot_size, round}
  payload: Record<string, unknown>
}

export interface Counters {
  transmissions: number
  events: number
  cards_open: number
  cards_total: number
  cards_queued: number
  unacked: number
  held: number
  pushed: number
  checker_rejections: number
  agent_wakes: number
  fallback_routes: number
}

export interface State {
  scenario_id: string
  mode: Mode
  lang: Lang
  running: boolean
  t: number
  strategy: Strategy
  strategy_event_id: string | null
  units: Record<string, Unit>
  zones: Record<string, Zone>
  transmissions: Transmission[]
  events: Event[]
  cards: Card[]
  proposals: Proposal[]
  briefs: Brief[]
  trace: TraceEntry[]
  counters: Counters
  // scenario yaml / zones.json: {floors, height_m, footprint_m | footprint, collapse_ring: {center, radius_m, label_ko, label_en}}
  building: Record<string, unknown>
  thresholds: Record<string, number>
}

// ----- ephemeral WS payloads (not part of State)
// `seq` is assigned client-side by ws.ts reduce (monotonic, survives the 50-item cap and run resets)
export interface Ping { unit_id: string; n: number; t: number; ping_id: string; seq?: number }
export interface Ask { unit_id: string; field: string; text: string; t: number; seq?: number }
export interface AudioCue { channel: Channel; line_id: string | null; audio_url: string; t: number; seq?: number }
export interface Escalation { card_id: string; level: number; t: number; seq?: number }
export interface ClockMsg { t: number; running: boolean; mode: Mode }
export interface StrategyMsg { strategy: Strategy; event_id: string | null }
// REPLAY only: a recorded REST action re-shown as a toast (server/cache.py RunReplayer)
export interface ToastMsg { method: string; path: string; body?: unknown; t?: number }

export type WsMessage =
  | { type: "snapshot"; payload: State }
  | { type: "clock"; payload: ClockMsg }
  | { type: "transmission"; payload: Transmission }
  | { type: "event"; payload: Event }
  | { type: "card"; payload: Card }
  | { type: "proposal"; payload: Proposal }
  | { type: "brief"; payload: Brief }
  | { type: "unit"; payload: Unit }
  | { type: "zone"; payload: Zone }
  | { type: "trace"; payload: TraceEntry }
  | { type: "counters"; payload: Counters }
  | { type: "audio_cue"; payload: AudioCue }
  | { type: "escalation"; payload: Escalation }
  | { type: "ping"; payload: Ping }
  | { type: "ask"; payload: Ask }
  | { type: "strategy"; payload: StrategyMsg }
  | { type: "toast"; payload: ToastMsg }

export interface ScenarioStartBody {
  mode: Mode
  lang?: Lang
  audio?: "radio" | "clean"
  run?: string
  scenario?: string
}

export interface RunInfo { file: string; size: number; t_max: number | null; mtime: number | string | null; best: boolean }
export interface PromoteResult { promoted: string; best: string; size: number; t_max: number | null }

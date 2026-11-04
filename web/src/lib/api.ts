// Fetch wrappers for every REST route in docs/CONTRACT.md.
import type {
  Brief, Card, CrewButton, Event, PromoteResult, Proposal, RunInfo, ScenarioStartBody, State, Transmission, Unit,
} from "./types"
import { isSampleMode } from "./ws"

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  // ?sample=1: no backend calls at all (no 502 spam in the console)
  if (isSampleMode()) throw new Error("sample mode: backend disabled")
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = ""
    try {
      detail = await res.text()
    } catch {
      /* ignore */
    }
    throw new Error(`${method} ${path} → ${res.status} ${detail.slice(0, 200)}`)
  }
  return (await res.json()) as T
}

/** The body is sent exactly as given (the Launcher builds it and shows it before sending). */
export const startScenario = (b: ScenarioStartBody) => req<State>("POST", "/api/scenario/start", b)
export const listRuns = () => req<RunInfo[]>("GET", "/api/runs")
export const promoteRun = (file: string) =>
  req<PromoteResult>("POST", `/api/runs/${encodeURIComponent(file)}/promote`, {})
export const stopScenario = () => req<State>("POST", "/api/scenario/stop", {})
export const resetScenario = () => req<State>("POST", "/api/scenario/reset", {})
export const getState = () => req<State>("GET", "/api/state")

export const ackCard = (id: string) => req<Card>("POST", `/api/cards/${encodeURIComponent(id)}/ack`, {})
export const resolveCard = (id: string, note?: string) =>
  req<Card>("POST", `/api/cards/${encodeURIComponent(id)}/resolve`, note ? { note } : {})

export const approveProposal = (id: string) =>
  req<Proposal>("POST", `/api/proposals/${encodeURIComponent(id)}/approve`, {})
export const rejectProposal = (id: string) =>
  req<Proposal>("POST", `/api/proposals/${encodeURIComponent(id)}/reject`, {})
export const editProposal = (id: string, text: string) =>
  req<Proposal>("PATCH", `/api/proposals/${encodeURIComponent(id)}`, { text })

export const crewButton = (unit: string, kind: CrewButton) =>
  req<Event>("POST", `/api/crew/${encodeURIComponent(unit)}/button`, { kind })
export const crewPtt = (unit: string, clipId: string) =>
  req<Transmission>("POST", `/api/crew/${encodeURIComponent(unit)}/ptt`, { clip_id: clipId })
export const crewAck = (unit: string) => req<Unit>("POST", `/api/crew/${encodeURIComponent(unit)}/ack`, {})

// eval/results.json — shape owned by eval/run_eval.py
export const getEvalResults = () => req<Record<string, unknown>>("GET", "/api/eval/results")

export interface ScenarioLine {
  id: string
  t?: number
  channel?: string
  unit?: string
  text?: string
  text_en?: string
  [k: string]: unknown
}
// TODO(main.py): confirm response shape; accept either a bare list or {lines: [...]}.
export async function getScenarioLines(): Promise<ScenarioLine[]> {
  const r = await req<ScenarioLine[] | { lines: ScenarioLine[] }>("GET", "/api/scenario/lines")
  return Array.isArray(r) ? r : (r?.lines ?? [])
}

export type { Brief }

// One WebSocket to /ws feeding a tiny external store (useSyncExternalStore; no deps).
// `?sample=1` on any route loads src/data/state_sample.json instead of connecting.
import { useSyncExternalStore } from "react"
import { toast } from "sonner"
import sampleJson from "@/data/state_sample.json"
import type { Ask, AudioCue, Brief, Escalation, Ping, State, WsMessage } from "./types"

export interface EarshotStore {
  state: State | null
  connected: boolean
  sample: boolean
  pings: Ping[]
  asks: Ask[]
  audioCues: AudioCue[]
  escalations: Escalation[]
  lastBriefByUnit: Record<string, Brief | undefined>
  /** bumps on every fresh-run snapshot (start / reset / REPLAY): card ids restart at card_0001, so client-side
   *  dedupe (escalation tones, toasts) is keyed by `${epoch}:...` */
  epoch: number
  /** last sequence number given to an ephemeral item (pings / asks / audioCues / escalations) */
  seq: number
}

const EPHEMERAL_MAX = 50

let snap: EarshotStore = {
  state: null,
  connected: false,
  sample: false,
  pings: [],
  asks: [],
  audioCues: [],
  escalations: [],
  lastBriefByUnit: {},
  epoch: 0,
  seq: 0,
}
const listeners = new Set<() => void>()
let started = false
let ws: WebSocket | null = null
let retryMs = 500

function emit(next: Partial<EarshotStore>) {
  snap = { ...snap, ...next }
  listeners.forEach((l) => l())
}

function upsertById<T extends { id: string }>(arr: T[], item: T): T[] {
  const i = arr.findIndex((x) => x.id === item.id)
  if (i < 0) return [...arr, item]
  const copy = arr.slice()
  copy[i] = item
  return copy
}

function pushCapped<T>(arr: T[], item: T): T[] {
  const next = [...arr, item]
  return next.length > EPHEMERAL_MAX ? next.slice(next.length - EPHEMERAL_MAX) : next
}

function briefsByUnit(briefs: Brief[]): Record<string, Brief | undefined> {
  const out: Record<string, Brief | undefined> = {}
  for (const b of briefs) {
    if (b.decision !== "push") continue
    const prev = out[b.unit_id]
    if (!prev || prev.created_t <= b.created_t) out[b.unit_id] = b
  }
  return out
}

/** A snapshot of a different run than the one on screen: fewer events/cards, the clock went back, or another
 *  scenario / mode. A reconnect refetch of the same run is not fresh. */
function isFreshRun(prev: State | null, next: State): boolean {
  if (!prev) return false
  return (
    (next.events?.length ?? 0) < (prev.events?.length ?? 0) ||
    (next.cards?.length ?? 0) < (prev.cards?.length ?? 0) ||
    next.t < prev.t - 1 ||
    next.mode !== prev.mode ||
    next.scenario_id !== prev.scenario_id ||
    ((next.events?.length ?? 0) === 0 && (prev.events?.length ?? 0) > 0)
  )
}

/** Pure reducer, exported for tests/other screens. */
export function reduce(s: EarshotStore, msg: WsMessage): EarshotStore {
  const st = s.state
  const now = st?.t ?? 0
  const seq = s.seq + 1
  switch (msg.type) {
    case "snapshot": {
      const base = { ...s, state: msg.payload, lastBriefByUnit: briefsByUnit(msg.payload.briefs ?? []) }
      if (!isFreshRun(st, msg.payload)) return base
      // new run: drop the previous run's stale asks / pings / escalations / cues
      return { ...base, epoch: s.epoch + 1, asks: [], pings: [], escalations: [], audioCues: [] }
    }
    case "audio_cue":
      return { ...s, seq, audioCues: pushCapped(s.audioCues, { ...msg.payload, t: msg.payload.t ?? now, seq }) }
    case "ping":
      return { ...s, seq, pings: pushCapped(s.pings, { ...msg.payload, t: msg.payload.t ?? now, seq }) }
    case "ask":
      return { ...s, seq, asks: pushCapped(s.asks, { ...msg.payload, t: msg.payload.t ?? now, seq }) }
    case "escalation":
      return { ...s, seq, escalations: pushCapped(s.escalations, { ...msg.payload, t: msg.payload.t ?? now, seq }) }
  }
  if (!st) return s
  switch (msg.type) {
    case "clock":
      return { ...s, state: { ...st, t: msg.payload.t, running: msg.payload.running, mode: msg.payload.mode ?? st.mode } }
    case "transmission":
      return { ...s, state: { ...st, transmissions: upsertById(st.transmissions, msg.payload) } }
    case "event":
      return { ...s, state: { ...st, events: upsertById(st.events, msg.payload) } }
    case "card":
      return { ...s, state: { ...st, cards: upsertById(st.cards, msg.payload) } }
    case "proposal":
      return { ...s, state: { ...st, proposals: upsertById(st.proposals, msg.payload) } }
    case "trace":
      return { ...s, state: { ...st, trace: upsertById(st.trace, msg.payload) } }
    case "brief": {
      const b = msg.payload
      const lb = { ...s.lastBriefByUnit }
      if (b.decision === "push") lb[b.unit_id] = b
      return { ...s, state: { ...st, briefs: upsertById(st.briefs, b) }, lastBriefByUnit: lb }
    }
    case "unit":
      return { ...s, state: { ...st, units: { ...st.units, [msg.payload.id]: msg.payload } } }
    case "zone":
      return { ...s, state: { ...st, zones: { ...st.zones, [msg.payload.id]: msg.payload } } }
    case "counters":
      return { ...s, state: { ...st, counters: msg.payload } }
    case "strategy":
      return { ...s, state: { ...st, strategy: msg.payload.strategy, strategy_event_id: msg.payload.event_id ?? null } }
  }
  return s
}

async function refetchState() {
  if (isSampleMode()) return
  try {
    const res = await fetch("/api/state")
    if (res.ok) {
      const st = (await res.json()) as State
      emit(reduce(snap, { type: "snapshot", payload: st }))
    }
  } catch {
    /* backend down; WS retry loop will try again */
  }
}

function connect() {
  if (isSampleMode()) return
  const proto = location.protocol === "https:" ? "wss" : "ws"
  ws = new WebSocket(`${proto}://${location.host}/ws`)
  ws.onopen = () => {
    retryMs = 500
    emit({ connected: true })
    void refetchState()
  }
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data as string) as WsMessage
      if (msg.type === "toast") toast.info(`REPLAY · ${msg.payload.method} ${msg.payload.path}`)
      const next = reduce(snap, msg)
      if (next !== snap) {
        snap = next
        listeners.forEach((l) => l())
      }
    } catch {
      /* ignore malformed frame */
    }
  }
  ws.onclose = () => {
    ws = null
    emit({ connected: false })
    setTimeout(connect, retryMs)
    retryMs = Math.min(retryMs * 2, 5000)
  }
  ws.onerror = () => {
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
  }
}

export function isSampleMode(): boolean {
  if (typeof window === "undefined") return false
  return new URLSearchParams(window.location.search).get("sample") === "1"
}

function start() {
  if (started) return
  started = true
  if (isSampleMode()) {
    const st = sampleJson as unknown as State
    const esc = st.cards
      .filter((c) => c.escalation_level > 0)
      .map((c) => ({ card_id: c.id, level: c.escalation_level, t: st.t }))
    emit({
      state: st,
      sample: true,
      connected: false,
      escalations: esc,
      pings: [{ unit_id: "park", n: 1, t: st.t - 3, ping_id: "ping_0001" }],
      asks: [{ unit_id: "kim", field: "needs", text: "필요한 것이 무엇입니까? 사다리, 공기용기 등", t: st.t - 2, seq: 1 }],
      seq: 1,
      lastBriefByUnit: briefsByUnit(st.briefs),
    })
    return
  }
  connect()
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  start()
  return () => {
    listeners.delete(cb)
  }
}

const getSnapshot = () => snap

export function useEarshot(): EarshotStore {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

/** Apply a REST response locally (e.g. after ack) so the UI updates even before the WS echo / in sample mode. */
export function applyLocal(msg: WsMessage) {
  emit(reduce(snap, msg))
}

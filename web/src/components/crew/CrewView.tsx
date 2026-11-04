import { useEffect, useMemo, useRef, useState } from "react"
import { Ear, Mic, Volume2 } from "lucide-react"
import { useEarshot } from "@/lib/ws"
import * as api from "@/lib/api"
import { speak } from "@/lib/tts"
import { tagLabel } from "@/lib/format"
import type { Brief } from "@/lib/types"
import { cn } from "@/lib/utils"
import HoldButton from "./HoldButton"
import EarpieceLine from "./EarpieceLine"

// TODO(main.py): relies on /api/scenario/lines carrying `kind` or `channel` per line
type ScenarioLine = { id: string; t?: number; unit?: string; kind?: unknown; channel?: unknown }

function normaliseLines(raw: unknown): ScenarioLine[] {
  if (Array.isArray(raw)) return raw as ScenarioLine[]
  if (raw && typeof raw === "object" && Array.isArray((raw as { lines?: unknown }).lines)) {
    return (raw as { lines: ScenarioLine[] }).lines
  }
  return []
}

const BUTTONS = [
  { kind: "EVACUATE", label: "긴급탈출", tone: "red" },
  { kind: "VICTIM_HERE", label: "구조대상자 여기", tone: "amber" },
  { kind: "SEARCH_DONE", label: "검색완료", tone: "green" },
  { kind: "NEED_HELP", label: "지원요청", tone: "blue" },
] as const

/**
 * Crew clip-on display. WS mapping (useEarshot):
 *  state.units[unitId]                       → header (callsign + name, zone label_ko, heard N of M)
 *  state.briefs ∪ lastBriefByUnit[unitId]    → latest push = body (spoken via browser TTS); holds → "held N"
 *  state.events[brief.evidence_event_id].triage.tag → tag chip ("규칙 Rn" only when the reason names a rule;
 *                                             IC-approved proposals → "IC 승인")
 *  asks (unit_id == unitId, newest)          → question card
 *  pings (unit_id == unitId, newest)         → 확인 chip → api.crewAck (hidden once unit.unanswered_pings == 0)
 */
export default function CrewView({ unitId, speakBriefs = true }: { unitId: string; speakBriefs?: boolean }) {
  const { state, connected, pings, asks, lastBriefByUnit } = useEarshot()
  const unit = state?.units?.[unitId]
  const zone = unit?.zone_id ? state?.zones?.[unit.zone_id] : undefined

  // --- briefs for this unit (merge snapshot list with the live last brief)
  const { latestPush, heldCount } = useMemo(() => {
    const mine: Brief[] = (state?.briefs ?? []).filter((b) => b.unit_id === unitId)
    const live = lastBriefByUnit?.[unitId]
    if (live && !mine.some((b) => b.id === live.id)) mine.push(live)
    const pushes = mine.filter((b) => b.decision === "push")
    return {
      latestPush: pushes.length ? pushes[pushes.length - 1] : undefined,
      heldCount: mine.filter((b) => b.decision === "hold").length,
    }
  }, [state?.briefs, lastBriefByUnit, unitId])

  // tag chip for the brief
  let tagKey = "ROUTINE"
  let tagText = "참고"
  if (latestPush) {
    const ev = latestPush.evidence_event_id
      ? state?.events?.find((e) => e.id === latestPush.evidence_event_id)
      : undefined
    const rule = /\bR[1-5]\b/.exec(latestPush.reason ?? "")
    const approved = /^IC approved/.test(latestPush.reason ?? "")
    if (ev) {
      tagKey = ev.triage.tag
      tagText = tagLabel(ev.triage.tag, state?.lang ?? "ko")
      if (approved) tagText = `${tagText} · IC 승인`
    } else if (latestPush.source === "rule" && rule) {
      tagKey = "RULE"
      tagText = `규칙 ${rule[0]}`
    } else if (approved) {
      tagText = "IC 승인"
    } else {
      tagText = latestPush.priority
    }
  }

  // --- speak new push briefs (not the one already present on first render)
  const [speaking, setSpeaking] = useState(false)
  const [pulse, setPulse] = useState(false)
  const spokenId = useRef<string | undefined>(undefined)
  const firstRun = useRef(true)
  const lang = state?.lang ?? "ko"
  const hasState = state != null
  useEffect(() => {
    const id = latestPush?.id
    if (!hasState) return
    if (firstRun.current) {
      firstRun.current = false
      spokenId.current = id
      return
    }
    if (!id || id === spokenId.current || !latestPush) return
    spokenId.current = id
    // speak() is fire-and-forget (queued behind any utterance in flight); animate for ~4 s
    if (speakBriefs) speak(latestPush.text, lang)
    const t0 = window.setTimeout(() => {
      setPulse(true)
      setSpeaking(speakBriefs)
    }, 0)
    const t1 = window.setTimeout(() => {
      setPulse(false)
      setSpeaking(false)
    }, 4000)
    return () => {
      window.clearTimeout(t0)
      window.clearTimeout(t1)
    }
  }, [latestPush, lang, speakBriefs, hasState])

  // --- pending ask / ping
  // tracked by the ask's seq (not its array index: the list is capped at 50 and cleared on a new run)
  const [doneAsks, setDoneAsks] = useState<Set<number>>(() => new Set())
  const askList = asks ?? []
  let lastAsk: (typeof askList)[number] | undefined
  for (let i = askList.length - 1; i >= 0; i--) {
    if (askList[i].unit_id === unitId) {
      lastAsk = askList[i]
      break
    }
  }
  const askSeq = lastAsk?.seq ?? -1
  const pendingAsk = lastAsk && !doneAsks.has(askSeq) ? lastAsk : undefined

  const [ackedPings, setAckedPings] = useState<Set<string>>(() => new Set())
  const myPings = (pings ?? []).filter((p) => p.unit_id === unitId)
  const lastPing = myPings[myPings.length - 1]
  const pendingPing =
    lastPing && !ackedPings.has(lastPing.ping_id) && (unit?.unanswered_pings ?? 1) > 0 ? lastPing : undefined

  // --- PTT clip from the scenario (next kind=ptt line for this unit)
  const [lines, setLines] = useState<ScenarioLine[]>([])
  const [usedClips, setUsedClips] = useState<Set<string>>(() => new Set())
  useEffect(() => {
    let alive = true
    Promise.resolve(api.getScenarioLines())
      .then((r: unknown) => {
        if (alive) setLines(normaliseLines(r))
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])
  // a clip the scenario already played over PTT (L06 at t=56) is a transmission already: never offer it again
  const playedClips = new Set((state?.transmissions ?? []).map((t) => t.line_id).filter(Boolean) as string[])
  const nextClip = lines.find(
    (l) =>
      (l.kind === "ptt" || l.channel === "PTT") && l.unit === unitId && !usedClips.has(l.id) && !playedClips.has(l.id),
  )
  const [talking, setTalking] = useState(false)
  const [pttMsg, setPttMsg] = useState<string | null>(null)

  const releaseTalk = async () => {
    if (!talking) return
    setTalking(false)
    if (!nextClip) {
      setPttMsg("no pre-recorded clip")
      return
    }
    const id = nextClip.id
    setUsedClips((s) => new Set(s).add(id))
    if (askSeq >= 0) setDoneAsks((s) => new Set(s).add(askSeq))
    setPttMsg(`sent ${id}`)
    try {
      await api.crewPtt(unitId, id)
    } catch (e) {
      setPttMsg("PTT failed")
      console.error(e)
    }
  }

  if (!state) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-zinc-400">
        {connected ? "waiting for snapshot…" : "connecting…"}
      </div>
    )
  }
  if (!unit) {
    return <div className="flex flex-1 items-center justify-center p-6 text-zinc-400">unknown unit “{unitId}”</div>
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pt-10 pb-3">
      {/* header */}
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xl font-bold">
            {unit.callsign}
            {unit.name ? ` ${unit.name}` : ""}
          </div>
          <div className="truncate text-sm text-zinc-400">
            {zone?.label_ko ?? unit.zone_id ?? "위치 미상"} · {unit.status}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] font-bold",
                state.mode === "LIVE" ? "bg-red-600" : "bg-zinc-600",
              )}
            >
              {state.mode}
            </span>
            {speaking ? (
              <Volume2 className="size-6 animate-pulse text-yellow-300" />
            ) : (
              <Ear className={cn("size-6", connected ? "text-zinc-300" : "text-zinc-600")} />
            )}
          </div>
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-semibold tabular-nums">
            heard {unit.heard_count} of {unit.total_count}
          </span>
          <span className="text-[10px] text-zinc-500 tabular-nums">held {heldCount}</span>
        </div>
      </header>

      {/* ping */}
      {pendingPing && (
        <button
          type="button"
          onClick={() => {
            setAckedPings((s) => new Set(s).add(pendingPing.ping_id))
            void Promise.resolve(api.crewAck(unitId)).catch((e: unknown) => console.error(e))
          }}
          className="flex animate-pulse items-center justify-between rounded-2xl border-2 border-yellow-300 bg-yellow-400 px-4 py-3 text-black"
        >
          <span className="text-lg font-bold">지휘대 호출 #{pendingPing.n}</span>
          <span className="rounded-lg bg-black px-3 py-1 text-lg font-bold text-yellow-300">확인</span>
        </button>
      )}

      {/* ask */}
      {pendingAsk && (
        <div className="rounded-2xl border-2 border-sky-400 bg-sky-950 p-3">
          <div className="text-xs font-semibold text-sky-300 uppercase">IC asks · {pendingAsk.field}</div>
          <div className="text-xl font-bold break-keep">{pendingAsk.text}</div>
          <div className="mt-1 text-xs text-sky-300">hold TALK to answer</div>
        </div>
      )}

      {/* body: latest pushed brief */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {latestPush ? (
          <EarpieceLine key={latestPush.id} brief={latestPush} tagKey={tagKey} tagText={tagText} pulse={pulse} />
        ) : (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-zinc-800 text-zinc-500">
            No briefs — quiet is good.
          </div>
        )}
      </div>

      {/* buttons */}
      <div className="flex flex-col gap-2">
        {BUTTONS.map((b) => (
          <HoldButton key={b.kind} label={b.label} tone={b.tone} onConfirm={() => api.crewButton(unitId, b.kind)} />
        ))}
        <button
          type="button"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture?.(e.pointerId)
            setTalking(true)
            setPttMsg(null)
          }}
          onPointerUp={() => void releaseTalk()}
          onPointerCancel={() => setTalking(false)}
          onContextMenu={(e) => e.preventDefault()}
          className={cn(
            "flex w-full touch-none items-center justify-between rounded-2xl border-2 px-4 py-3 select-none",
            talking ? "scale-[0.98] border-red-400 bg-red-950 text-red-200" : "border-zinc-600 bg-zinc-800 text-zinc-100",
          )}
        >
          <span className="flex items-center gap-2 text-2xl font-bold">
            <Mic className="size-6" />
            {talking ? "● TALK" : "TALK"}
          </span>
          <span className="text-right text-[11px] text-zinc-400">
            {pttMsg ?? (nextClip ? `pre-recorded clip ${nextClip.id} (MVP)` : "no clip left")}
          </span>
        </button>
      </div>

      <footer className="text-center text-[10px] text-zinc-500">Simulated clip-on display · TTS: browser (non-Meta)</footer>
    </div>
  )
}

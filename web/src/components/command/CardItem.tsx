import { useEffect } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { ackCard, resolveCard } from "@/lib/api"
import { fmtClock, fmtLatency, MAYDAY_ORDERS, R1_KEYS, R1L2_KEYS, tagBorder, tagColor, tagLabel, threshold } from "@/lib/format"
import { applyLocal, useEarshot } from "@/lib/ws"
import type { Card, Proposal, State } from "@/lib/types"
import { ProposalItem } from "./ProposalItem"

const FIELD_ORDER: Record<string, string[]> = {
  MAYDAY: ["who", "what", "where", "needs", "air"],
  RULE: ["who", "what", "where", "needs", "air"],
  VICTIM_FOUND: ["count", "where", "state"],
  DANGER: ["where", "terms"],
  HELP_NEEDED: ["who", "where", "needs"],
}

// ---- WebAudio alert tone, once per (run epoch, card, level)
const played = new Set<string>()
let ctx: AudioContext | null = null
// Autoplay policy: a context created before any user gesture starts suspended. Create / resume it on the first
// pointerdown anywhere, so the first escalation after any click is audible.
if (typeof document !== "undefined") {
  const unlock = () => {
    try {
      ctx ??= new AudioContext()
      if (ctx.state === "suspended") void ctx.resume()
    } catch {
      /* no audio */
    }
  }
  document.addEventListener("pointerdown", unlock, { once: true, capture: true })
  document.addEventListener("keydown", unlock, { once: true, capture: true })
}
function beep(level: number) {
  try {
    ctx ??= new AudioContext()
    if (ctx.state === "suspended") void ctx.resume()
    const n = level >= 2 ? 3 : 2
    for (let i = 0; i < n; i++) {
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.type = "square"
      o.frequency.value = level >= 2 ? 1320 : 990
      const t0 = ctx.currentTime + i * 0.22
      g.gain.setValueAtTime(0.0001, t0)
      g.gain.exponentialRampToValueAtTime(0.25, t0 + 0.01)
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.16)
      o.connect(g).connect(ctx.destination)
      o.start(t0)
      o.stop(t0 + 0.18)
    }
  } catch {
    /* no audio */
  }
}

async function act(p: Promise<Card>, label: string) {
  try {
    applyLocal({ type: "card", payload: await p })
  } catch (e) {
    toast.error(`${label} failed`, { description: String(e) })
  }
}

/** Card latency split into "after end of transmission" (primary) and "after key-up" (includes the clip itself). */
function cardLatency(card: Card, state: State) {
  const total = card.latency_ms
  const ev0 = state.events.find((e) => e.id === card.event_ids[0])
  const tx = ev0 ? state.transmissions.find((t) => t.id === ev0.transmission_id) : undefined
  const clipS = tx?.t_end != null && Number.isFinite(tx.t_end) ? Math.max(0, tx.t_end - tx.t_keyup) : null
  let after: number | null = null
  let exact = true
  let clip = clipS
  if (card.latency_after_speech_ms != null && Number.isFinite(card.latency_after_speech_ms)) {
    after = card.latency_after_speech_ms
    if (clip == null && Number.isFinite(total)) clip = Math.max(0, (total - after) / 1000)
  }  else if (clipS != null && Number.isFinite(total)) after = Math.max(0, total - clipS * 1000)
  else {
    after = total
    exact = false
  }
  return { after, total, clipS: clip, exact }
}

export function CardItem({ card, state, proposals }: { card: Card; state: State; proposals: Proposal[] }) {
  const kindKey = card.kind
  const isMaydayLike = card.kind === "MAYDAY" || (card.kind === "RULE" && card.priority === 0)
  const live = card.state === "open" || card.state === "escalated"
  const lvl = card.escalation_level
  const { epoch } = useEarshot()

  useEffect(() => {
    if (lvl < 1 || !live) return
    const key = `${epoch}:${card.id}:${lvl}`
    if (played.has(key)) return
    played.add(key)
    beep(lvl)
  }, [epoch, card.id, lvl, live])

  const r1 = threshold(state.thresholds, R1_KEYS, 10)
  const r1l2 = threshold(state.thresholds, R1L2_KEYS, 20)
  const age = Math.max(0, state.t - card.created_t)
  const pct = Math.min(100, (age / r1l2) * 100)

  const lat = cardLatency(card, state)
  const ev = state.events.find((e) => e.id === card.event_ids[card.event_ids.length - 1])
  const fields = FIELD_ORDER[kindKey] ?? Object.keys(card.fields)
  const keys = Array.from(new Set([...fields, ...Object.keys(card.fields)]))

  return (
    <article
      className={
        "rounded-lg border-2 bg-zinc-900 p-3 shadow-lg " +
        tagBorder(card.kind) +
        (lvl >= 1 && live ? " escalate-pulse" : "") +
        (live ? "" : " opacity-60")
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={"rounded-md border px-2 py-0.5 text-xl font-black " + tagColor(card.kind)}>
          {card.kind === "RULE" ? `규칙 ${card.rule_id ?? ""}` : tagLabel(card.kind, "ko")}
        </span>
        <span className="text-xs font-semibold tracking-wide text-zinc-400">{tagLabel(card.kind, "en")}</span>
        {lvl > 0 && live && (
          <span className="rounded bg-red-600 px-1.5 py-0.5 text-xs font-bold text-white">ESC L{lvl}</span>
        )}
        <span
          className="ml-auto flex flex-col items-end rounded bg-zinc-800 px-2 py-0.5 font-mono leading-tight"
          title="measured: end of transmission → card (primary) · key-up → card (includes the clip itself)"
        >
          <span className="text-sm font-bold text-emerald-300">
            {fmtLatency(lat.after)} {lat.exact ? "after end of transmission" : "after key-up"}
          </span>
          {lat.exact && (
            <span className="text-[11px] text-zinc-400">
              {fmtLatency(lat.total)} after key-up{lat.clipS != null ? ` · clip ${lat.clipS.toFixed(1)} s` : ""}
            </span>
          )}
        </span>
      </div>
      <h3 className="mt-1.5 text-xl font-bold leading-tight text-white">{card.title}</h3>
      {card.title_en && <p className="text-sm text-zinc-400">{card.title_en}</p>}

      {keys.length > 0 && (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[15px]">
          {keys.map((k) => {
            const v = card.fields[k]
            const missing = card.missing_fields.includes(k) || v == null
            return (
              <div key={k} className="contents">
                <dt className="font-mono text-zinc-400 uppercase">{k}</dt>
                <dd
                  className={
                    missing
                      ? "rounded bg-red-950/70 px-1 font-semibold text-red-300 ring-1 ring-red-500"
                      : "text-zinc-100"
                  }
                >
                  {missing ? "— missing" + (k === "air" ? " (optional)" : "") : v}
                </dd>
              </div>
            )
          })}
        </dl>
      )}

      {card.evidence_span && (
        <Tooltip>
          <TooltipTrigger
            render={
              <blockquote className="mt-2 cursor-help border-l-4 border-zinc-500 pl-2 text-[15px] text-zinc-200 italic" />
            }
          >
            “{card.evidence_span}”
          </TooltipTrigger>
          <TooltipContent className="max-w-md text-sm">
            {ev ? ev.text : "evidence span (verbatim from transcript)"}
            {ev && !ev.evidence_verified && " · ⚠ span not verified verbatim"}
          </TooltipContent>
        </Tooltip>
      )}

      {card.rule_id && card.kind === "RULE" && card.note && <p className="mt-1 text-sm text-amber-300">{card.note}</p>}
      {card.kind !== "RULE" && card.note && <p className="mt-1 text-sm text-zinc-300">note: {card.note}</p>}

      <div className="mt-2 flex items-center gap-2 text-sm text-zinc-400">
        <span>{card.channel ?? "—"}</span>
        <span className="font-mono">{fmtClock(card.created_t)}</span>
        {card.rule_id && <span className="rounded bg-zinc-800 px-1 text-zinc-200">{card.rule_id}</span>}
        <span className="ml-auto uppercase">{card.state}</span>
      </div>

      {isMaydayLike && live && (
        <div className="mt-2">
          <div className="mb-1 flex justify-between text-xs text-zinc-400">
            <span>
              ack timer {Math.floor(age)} s · L1 {r1} s · L2 {r1l2} s
            </span>
            <span className="italic">demo timescale</span>
          </div>
          <Progress
            value={pct}
            className={age >= r1 ? "[&_[data-slot=progress-indicator]]:bg-red-500" : "[&_[data-slot=progress-indicator]]:bg-amber-400"}
          />
        </div>
      )}

      {live && (
        <div className="mt-3 flex gap-2">
          <Button
            size="lg"
            className="h-10 flex-1 bg-red-600 text-lg font-bold text-white hover:bg-red-500"
            onClick={() => act(ackCard(card.id), "ACK")}
          >
            ACK
          </Button>
          <Button size="lg" variant="outline" className="h-10" onClick={() => act(resolveCard(card.id), "Resolve")}>
            Resolve
          </Button>
        </div>
      )}

      {proposals.length > 0 && (
        <div className="mt-2 space-y-2">
          {[...proposals]
            .sort((a, b) => Number(MAYDAY_ORDERS.has(b.kind)) - Number(MAYDAY_ORDERS.has(a.kind)) || a.created_t - b.created_t)
            .map((p) => (
              <ProposalItem key={p.id} p={p} state={state} prominent={isMaydayLike && MAYDAY_ORDERS.has(p.kind)} />
            ))}
        </div>
      )}
    </article>
  )
}

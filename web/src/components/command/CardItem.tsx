import { useEffect } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { ackCard, resolveCard } from "@/lib/api"
import { fmtClock, fmtLatency, R1_KEYS, R1L2_KEYS, tagBorder, tagColor, tagLabel, threshold } from "@/lib/format"
import { applyLocal } from "@/lib/ws"
import type { Card, Proposal, State } from "@/lib/types"
import { ProposalItem } from "./ProposalItem"

const FIELD_ORDER: Record<string, string[]> = {
  MAYDAY: ["who", "what", "where", "needs", "air"],
  RULE: ["who", "what", "where", "needs", "air"],
  VICTIM_FOUND: ["count", "where", "state"],
  DANGER: ["where", "terms"],
  HELP_NEEDED: ["who", "where", "needs"],
}

// ---- WebAudio alert tone, once per (card, level)
const played = new Set<string>()
let ctx: AudioContext | null = null
export function beep(level: number) {
  try {
    ctx ??= new AudioContext()
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

export function CardItem({ card, state, proposals }: { card: Card; state: State; proposals: Proposal[] }) {
  const kindKey = card.kind
  const isMaydayLike = card.kind === "MAYDAY" || (card.kind === "RULE" && card.priority === 0)
  const live = card.state === "open" || card.state === "escalated"
  const lvl = card.escalation_level

  useEffect(() => {
    if (lvl < 1 || !live) return
    const key = `${card.id}:${lvl}`
    if (played.has(key)) return
    played.add(key)
    beep(lvl)
  }, [card.id, lvl, live])

  const r1 = threshold(state.thresholds, R1_KEYS, 10)
  const r1l2 = threshold(state.thresholds, R1L2_KEYS, 20)
  const age = Math.max(0, state.t - card.created_t)
  const pct = Math.min(100, (age / r1l2) * 100)

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
        <span className="ml-auto rounded bg-zinc-800 px-2 py-0.5 font-mono text-sm text-emerald-300" title="measured key-up → card">
          {fmtLatency(card.latency_ms)} after key-up
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
          {proposals.map((p) => (
            <ProposalItem key={p.id} p={p} state={state} />
          ))}
        </div>
      )}
    </article>
  )
}

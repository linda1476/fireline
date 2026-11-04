import { useState } from "react"
import { ChevronRight } from "lucide-react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { fmtClock } from "@/lib/format"
import type { State, TraceEntry, TraceKind } from "@/lib/types"

const KINDS: TraceKind[] = ["wake", "reasoning", "tool_call", "checker", "delivery", "fallback"]

function summary(e: TraceEntry): { text: string; tone: string } {
  const p = e.payload as Record<string, unknown>
  switch (e.kind) {
    case "wake":
      return { text: `wake · ${e.wake_reason}`, tone: "text-zinc-300" }
    case "reasoning":
      return { text: String(p.summary ?? "(no summary)"), tone: "text-zinc-300 italic" }
    case "tool_call": {
      const args = (p.args ?? {}) as Record<string, unknown>
      const tgt = args.unit_id ?? (Array.isArray(args.units) ? (args.units as string[]).join(",") : args.event_id) ?? ""
      const pri = args.priority ? ` ${String(args.priority)}` : ""
      return { text: `${String(p.tool ?? "?")}(${String(tgt)}${pri})`, tone: "font-mono text-sky-300" }
    }
    case "checker":
      return p.ok
        ? { text: `✓ ${String(p.tool ?? "")} ok`, tone: "text-emerald-400" }
        : { text: `✗ ${String(p.tool ?? "")} rejected: ${String(p.error ?? "")}`, tone: "font-semibold text-red-400" }
    case "delivery":
      return { text: `→ ${String(p.decision ?? "")} ${String(p.unit_id ?? "")} (${String(p.brief_id ?? "")})`, tone: "text-violet-300" }
    case "fallback":
      return { text: `fallback router · ${String(p.reason ?? "")}`, tone: "text-amber-300" }
  }
  return { text: e.kind, tone: "" }
}

export function TraceTab({ state }: { state: State }) {
  const [kinds, setKinds] = useState<string[]>(KINDS)
  const entries = state.trace.filter((e) => kinds.includes(e.kind)).sort((a, b) => a.t - b.t)
  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-2">
      <ToggleGroup multiple value={kinds} onValueChange={(v: unknown[]) => setKinds(v.map(String))} variant="outline" size="sm">
        {KINDS.map((k) => (
          <ToggleGroupItem key={k} value={k} className="px-2 text-xs">
            {k}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <div className="text-xs text-zinc-500">
        agent wakes {state.counters.agent_wakes} · checker rejections {state.counters.checker_rejections} · fallback{" "}
        {state.counters.fallback_routes}
      </div>
      <ScrollArea className="min-h-0 flex-1 rounded-md border border-border">
        <div className="divide-y divide-border/60">
          {entries.map((e) => {
            const s = summary(e)
            const bad = e.kind === "checker" && (e.payload as { ok?: boolean }).ok === false
            return (
              <Collapsible key={e.id} className={bad ? "bg-red-950/50" : ""}>
                <CollapsibleTrigger className="group flex w-full items-start gap-2 px-2 py-1.5 text-left text-sm hover:bg-zinc-900">
                  <ChevronRight className="mt-0.5 size-4 shrink-0 text-zinc-500 transition-transform group-data-[panel-open]:rotate-90" />
                  <span className="w-10 shrink-0 font-mono text-xs text-zinc-500">{fmtClock(e.t)}</span>
                  <span className="w-16 shrink-0 text-xs uppercase text-zinc-500">{e.kind}</span>
                  <span className={"min-w-0 flex-1 break-words " + s.tone}>{s.text}</span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <pre className="mx-2 mb-2 overflow-x-auto rounded bg-zinc-900 p-2 text-xs whitespace-pre-wrap text-zinc-300">
                    {e.wake_id} · {e.wake_reason}
                    {"\n"}
                    {JSON.stringify(e.payload, null, 2)}
                  </pre>
                </CollapsibleContent>
              </Collapsible>
            )
          })}
          {entries.length === 0 && <p className="p-4 text-center text-sm text-zinc-500">No trace yet</p>}
        </div>
      </ScrollArea>
    </div>
  )
}

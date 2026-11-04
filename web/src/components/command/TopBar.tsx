import { useEffect, useState } from "react"
import { Link } from "react-router"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { fmtClock } from "@/lib/format"
import type { State } from "@/lib/types"

/** state.running, but never "stopped" while the clock is visibly advancing (clock frames can lag the flag). */
function useRunning(state: State): boolean {
  const [now, setNow] = useState(() => Date.now())
  const [prevT, setPrevT] = useState(state.t)
  const [advancedAt, setAdvancedAt] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  // adjust-state-on-prop-change: remember when the clock last moved forward
  if (state.t !== prevT) {
    setPrevT(state.t)
    setAdvancedAt(state.t > prevT ? now : 0)
  }
  return state.running || (advancedAt > 0 && now - advancedAt < 3500)
}

const STRATEGY_KO: Record<string, string> = { OFFENSIVE: "공격전략", DEFENSIVE: "방어전략", NONE: "전략 미정" }

export function TopBar({
  state,
  connected,
  sample,
  playRadio,
  onPlayRadio,
}: {
  state: State
  connected: boolean
  sample: boolean
  playRadio?: boolean
  onPlayRadio?: (v: boolean) => void
}) {
  const c = state.counters
  const running = useRunning(state)
  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-border bg-zinc-950 px-4 py-2">
      <Link to="/" className="text-lg font-bold tracking-tight text-zinc-100">
        Earshot <span className="font-normal text-muted-foreground">· IC</span>
      </Link>
      <div className="font-mono text-4xl font-bold tabular-nums text-white" title="incident clock (scenario seconds)">
        {fmtClock(state.t)}
      </div>
      <Badge
        className={
          "h-8 px-3 text-lg font-black tracking-wider " +
          (state.mode === "LIVE" ? "bg-red-600 text-white" : "bg-sky-600 text-white")
        }
      >
        {state.mode}
      </Badge>
      {running ? (
        <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-300">
          <span className="relative flex size-2.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex size-2.5 rounded-full bg-emerald-500" />
          </span>
          running
        </span>
      ) : (
        <span className="text-sm text-muted-foreground">stopped</span>
      )}
      <div className="text-base text-zinc-200 tabular-nums">
        transmissions <b className="text-white">{c.transmissions}</b> → cards <b className="text-white">{c.cards_total}</b>
        {" · "}held <b className="text-white">{c.held}</b>
        {" · "}unacked <b className={c.unacked > 0 ? "text-red-400" : "text-white"}>{c.unacked}</b>
      </div>
      <Badge
        variant="outline"
        className={
          "h-7 px-2.5 text-base " +
          (state.strategy === "OFFENSIVE"
            ? "border-orange-400 text-orange-300"
            : state.strategy === "DEFENSIVE"
              ? "border-sky-400 text-sky-300"
              : "text-muted-foreground")
        }
      >
        {STRATEGY_KO[state.strategy] ?? state.strategy} <span className="ml-1 text-xs opacity-70">{state.strategy}</span>
      </Badge>
      <div className="ml-auto flex items-center gap-4 text-sm">
        {onPlayRadio && (
          <label className="flex cursor-pointer items-center gap-2 text-zinc-300">
            <Switch checked={!!playRadio} onCheckedChange={(v) => onPlayRadio(!!v)} />
            play radio
          </label>
        )}
        <span className="flex items-center gap-1.5 text-zinc-300">
          <span
            className={
              "inline-block size-2.5 rounded-full " + (sample ? "bg-amber-400" : connected ? "bg-emerald-500" : "bg-red-500")
            }
          />
          {sample ? "sample data" : connected ? "connected" : "offline"}
        </span>
      </div>
    </header>
  )
}

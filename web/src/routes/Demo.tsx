import CommandView from "@/components/command/CommandView"
import PhoneFrame from "@/components/crew/PhoneFrame"
import CrewView from "@/components/crew/CrewView"
import { useEarshot } from "@/lib/ws"
import { cn } from "@/lib/utils"

const PHONES = [
  { unit: "kim", label: "FF Kim · 한빛구조대 · 2F east" },
  { unit: "park", label: "FF Park · 누리센터 · 1F west" },
]

/** /demo: CommandView 60% + two crew phones (kim, park) at 0.8 scale. */
export default function Demo() {
  const { state, connected, sample } = useEarshot()
  const mode = state?.mode ?? "LIVE"
  return (
    <div className="flex h-screen max-h-screen flex-col overflow-hidden bg-background text-foreground">
      <div className="flex items-center gap-3 border-b px-3 py-1 text-xs">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 font-bold text-white",
            mode === "LIVE" ? "bg-red-600" : "bg-zinc-600",
          )}
        >
          {mode}
        </span>
        <span className="text-muted-foreground">
          {mode === "LIVE"
            ? "Synthetic scenario · radio replayed · every model call live"
            : "Replay of a recorded live run"}
        </span>
        {!connected && !sample && <span className="ml-auto text-amber-500">reconnecting…</span>}
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[3fr_2fr]">
        <div className="min-h-0 min-w-0 overflow-hidden">
          <CommandView />
        </div>
        <div className="flex min-h-0 flex-wrap content-start items-start justify-center gap-3 overflow-auto bg-neutral-800 p-3">
          {PHONES.map((ph) => (
            <div key={ph.unit} className="flex flex-col items-center gap-1">
              <div className="rounded bg-zinc-900 px-2 py-0.5 text-sm font-semibold text-zinc-100">{ph.label}</div>
              <PhoneFrame scale={0.8}>
                <CrewView unitId={ph.unit} />
              </PhoneFrame>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

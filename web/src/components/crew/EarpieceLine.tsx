import type { Brief } from "@/lib/types"
import { cn } from "@/lib/utils"
import { actionHint } from "./actionHint"

const TAG_CHIP: Record<string, string> = {
  MAYDAY: "bg-red-600 text-white",
  DANGER: "bg-orange-500 text-black",
  VICTIM_FOUND: "bg-amber-400 text-black",
  HELP_NEEDED: "bg-sky-500 text-black",
  ROUTINE: "bg-zinc-600 text-white",
  RULE: "bg-fuchsia-600 text-white",
}

/** The latest pushed brief: tag chip · text · action hint · why. */
export default function EarpieceLine({
  brief,
  tagKey,
  tagText,
  pulse,
}: {
  brief: Brief
  tagKey: string
  tagText: string
  pulse: boolean
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-2xl border border-zinc-700 bg-zinc-900 p-4 animate-in fade-in slide-in-from-top-2 duration-300",
        pulse && "ring-2 ring-yellow-300",
      )}
    >
      <div className="flex items-center gap-2">
        <span className={cn("rounded-md px-2 py-0.5 text-sm font-bold", TAG_CHIP[tagKey] ?? TAG_CHIP.ROUTINE)}>{tagText}</span>
        <span className="text-xs font-semibold text-zinc-400">{brief.priority}</span>
      </div>
      <p className="text-[26px] leading-snug font-bold break-keep">{brief.text}</p>
      <p className="text-lg font-semibold text-yellow-300">{actionHint(tagKey, brief.priority)}</p>
      <p className="text-xs text-zinc-500">why: {brief.reason}</p>
    </div>
  )
}

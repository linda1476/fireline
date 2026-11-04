import { ScrollArea } from "@/components/ui/scroll-area"
import type { State } from "@/lib/types"
import { CardItem } from "./CardItem"
import { ProposalItem } from "./ProposalItem"

const MAX_SHOWN = 5

export function CardQueue({ state }: { state: State }) {
  const live = state.cards
    .filter((c) => c.state === "open" || c.state === "escalated")
    .sort((a, b) => a.priority - b.priority || a.created_t - b.created_t)
  const shown = live.slice(0, MAX_SHOWN)
  const queued = Math.max(live.length - shown.length, state.counters.cards_queued ?? 0)
  const shownIds = new Set(shown.map((c) => c.id))
  const pending = state.proposals.filter((p) => p.state === "pending" || p.state === "edited")
  const orphan = pending.filter((p) => !p.card_id || !shownIds.has(p.card_id))
  const acked = state.cards.filter((c) => c.state === "acked").length

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-baseline gap-3 bg-zinc-900 px-3 py-1">
        <h2 className="text-lg font-bold text-white">Cards</h2>
        <span className="text-sm text-zinc-400">
          open {live.length} · acked {acked}
        </span>
        {queued > 0 && <span className="ml-auto rounded bg-amber-500 px-2 text-sm font-bold text-black">+{queued} queued</span>}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-3">
          {shown.length === 0 && <p className="py-10 text-center text-lg text-zinc-500">No open cards</p>}
          {shown.map((c) => (
            <CardItem key={c.id} card={c} state={state} proposals={pending.filter((p) => p.card_id === c.id)} />
          ))}
          {orphan.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-zinc-400">Proposals</h3>
              {orphan.map((p) => (
                <ProposalItem key={p.id} p={p} state={state} />
              ))}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

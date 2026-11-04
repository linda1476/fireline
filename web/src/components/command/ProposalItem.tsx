import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { approveProposal, editProposal, rejectProposal } from "@/lib/api"
import { applyLocal } from "@/lib/ws"
import type { Proposal, State } from "@/lib/types"

const KIND_KO: Record<string, string> = {
  RADIO_SILENCE: "무전 통제",
  RIT_DEPLOY: "RIT 투입",
  WITHDRAW: "전원 철수",
  CONFIRM_STRATEGY: "전략 확인",
  ASSIGN: "임무 지정",
}

async function run<T extends Proposal>(p: Promise<T>, label: string) {
  try {
    const res = await p
    applyLocal({ type: "proposal", payload: res })
  } catch (e) {
    toast.error(`${label} failed`, { description: String(e) })
  }
}

const SOURCE_CHIP: Record<string, string> = {
  agent: "bg-violet-600 text-white",
  rule: "bg-fuchsia-700 text-white",
  router: "bg-zinc-600 text-white",
}

export function ProposalItem({ p, state, prominent = false }: { p: Proposal; state: State; prominent?: boolean }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(p.text)
  const units = p.units.map((u) => state.units[u]?.callsign ?? u).join(", ")
  return (
    <div
      className={
        prominent
          ? "rounded-md border-2 border-amber-400 bg-amber-950/50 p-2.5 shadow-md shadow-amber-900/40"
          : "rounded-md border border-dashed border-sky-500/70 bg-sky-950/40 p-2"
      }
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span
          className={
            "rounded px-1.5 py-0.5 font-bold " +
            (prominent ? "bg-amber-400 text-base text-black" : "bg-sky-600 text-white")
          }
        >
          제안 {KIND_KO[p.kind] ?? p.kind}
        </span>
        <span className={"text-xs " + (prominent ? "text-amber-300" : "text-sky-300")}>{p.kind}</span>
        <span
          className={"rounded px-1 py-px text-[10px] font-bold tracking-wide uppercase " + (SOURCE_CHIP[p.source] ?? SOURCE_CHIP.router)}
          title="who proposed it"
        >
          {p.source}
        </span>
        <span className="text-xs text-zinc-400">→ {units || "—"}</span>
        {p.state !== "pending" && <span className="ml-auto text-xs uppercase text-zinc-300">{p.state}</span>}
      </div>
      <p className={"mt-1 text-white " + (prominent ? "text-lg font-semibold" : "text-base")}>{p.text}</p>
      <p className="text-xs text-zinc-400">why: {p.rationale}</p>
      {(p.state === "pending" || p.state === "edited") && (
        <div className="mt-2 flex gap-2">
          <Button size="sm" className="bg-emerald-600 text-white hover:bg-emerald-500" onClick={() => run(approveProposal(p.id), "Approve")}>
            Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => run(rejectProposal(p.id), "Reject")}>
            Reject
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setText(p.text)
              setOpen(true)
            }}
          >
            Edit
          </Button>
        </div>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit proposal · {KIND_KO[p.kind] ?? p.kind}</DialogTitle>
          </DialogHeader>
          <Input value={text} onChange={(e) => setText(e.target.value)} className="text-base" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                setOpen(false)
                void run(editProposal(p.id, text), "Edit")
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

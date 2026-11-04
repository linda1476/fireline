import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { tagLabel } from "@/lib/format"
import { useEarshot } from "@/lib/ws"
import { AccountabilityStrip } from "./AccountabilityStrip"
import { CardQueue } from "./CardQueue"
import { ChannelLanes } from "./ChannelLanes"
import { MapTab } from "./MapTab"
import { TopBar } from "./TopBar"
import { TraceTab } from "./TraceTab"

const PLAY_KEY = "earshot.playRadio"
function readPlay(): boolean {
  try {
    return localStorage.getItem(PLAY_KEY) !== "0"
  } catch {
    return true
  }
}

/**
 * IC dashboard. `audioAutoPlay` plays audio_cue clips on the lanes (only the /command route sets it);
 * `toasts` shows sonner toasts for new cards / escalations / proposals.
 */
export default function CommandView({
  audioAutoPlay = false,
  toasts = true,
  className = "",
}: {
  audioAutoPlay?: boolean
  toasts?: boolean
  className?: string
}) {
  const { state, connected, sample, audioCues, escalations, epoch } = useEarshot()
  const [playRadio, setPlayRadio] = useState<boolean>(readPlay)
  const seen = useRef<Set<string> | null>(null)

  useEffect(() => {
    if (!state) return
    const keys: [string, () => void][] = []
    for (const c of state.cards)
      keys.push([`${epoch}:card:${c.id}`, () => toast.error(`${tagLabel(c.kind, "ko")} · new card`, { description: c.title })])
    for (const p of state.proposals)
      keys.push([`${epoch}:prop:${p.id}`, () => toast.info(`Proposal · ${p.kind}`, { description: p.text })])
    for (const e of escalations)
      keys.push([
        `${epoch}:esc:${e.card_id}:${e.level}`,
        () => {
          const c = state.cards.find((x) => x.id === e.card_id)
          toast.warning(`Escalation L${e.level}`, { description: c ? c.title : e.card_id })
        },
      ])
    if (seen.current == null) {
      seen.current = new Set(keys.map((k) => k[0]))
      return
    }
    for (const [k, fn] of keys) {
      if (seen.current.has(k)) continue
      seen.current.add(k)
      if (toasts) fn()
    }
  }, [state, escalations, toasts, epoch])

  if (!state) {
    return (
      <div className={"flex h-full items-center justify-center bg-background text-xl text-zinc-400 " + className}>
        {connected ? "Waiting for state…" : "Connecting to backend… (add ?sample=1 for sample data)"}
      </div>
    )
  }

  return (
    <div className={"flex h-full min-h-0 flex-col bg-background text-foreground " + className}>
      <TopBar
        state={state}
        connected={connected}
        sample={sample}
        playRadio={audioAutoPlay ? playRadio : undefined}
        onPlayRadio={
          audioAutoPlay
            ? (v) => {
                setPlayRadio(v)
                try {
                  localStorage.setItem(PLAY_KEY, v ? "1" : "0")
                } catch {
                  /* ignore */
                }
              }
            : undefined
        }
      />
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(260px,1fr)_minmax(360px,1.35fr)_minmax(320px,1.15fr)]">
        <div className="min-h-0 border-r border-border">
          <ChannelLanes state={state} audioCues={audioCues} autoPlay={audioAutoPlay && playRadio} />
        </div>
        <div className="min-h-0 border-r border-border">
          <CardQueue state={state} />
        </div>
        <div className="min-h-0">
          <Tabs defaultValue="map" className="flex h-full min-h-0 flex-col gap-0">
            <TabsList className="m-2 mb-0">
              <TabsTrigger value="map" className="px-4 text-base">
                Map
              </TabsTrigger>
              <TabsTrigger value="trace" className="px-4 text-base">
                Trace
              </TabsTrigger>
            </TabsList>
            <TabsContent value="map" className="min-h-0 flex-1">
              <MapTab state={state} />
            </TabsContent>
            <TabsContent value="trace" className="min-h-0 flex-1">
              <TraceTab state={state} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
      <div className="max-h-[32vh] shrink-0 overflow-auto border-t border-border">
        <AccountabilityStrip state={state} />
      </div>
    </div>
  )
}

export { CommandView }

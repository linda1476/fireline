import { useEffect, useRef } from "react"
import { Play } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { fmtClock } from "@/lib/format"
import type { AudioCue, Channel, State, Transmission } from "@/lib/types"

const LANES: { ch: Channel; ko: string; en: string; also?: Channel }[] = [
  { ch: "CMD", ko: "지휘망", en: "CMD" },
  { ch: "TAC", ko: "작전망", en: "TAC", also: "PTT" },
]

function TxRow({ tx, state, onPlay }: { tx: Transmission; state: State; onPlay: (tx: Transmission) => void }) {
  const u = tx.unit_id ? state.units[tx.unit_id] : undefined
  const final = tx.text_final != null
  return (
    <div className="border-b border-border/60 px-2 py-2">
      <div className="flex items-center gap-2 text-sm text-zinc-400">
        <span className="font-mono tabular-nums">{fmtClock(tx.t_keyup)}</span>
        <span className="font-semibold text-zinc-200">{u ? u.callsign : (tx.unit_id ?? "unknown")}</span>
        {u?.name && <span className="text-zinc-400">{u.name}</span>}
        {tx.channel === "PTT" && <span className="rounded bg-zinc-700 px-1 text-xs text-zinc-200">PTT</span>}
        {tx.line_id && <span className="text-xs text-zinc-500">{tx.line_id}</span>}
        {tx.audio_url && (
          <button
            type="button"
            className="ml-auto rounded p-1 text-zinc-300 hover:bg-zinc-800 hover:text-white"
            onClick={() => onPlay(tx)}
            title="play clip"
          >
            <Play className="size-4" />
          </button>
        )}
      </div>
      <p className={"mt-0.5 text-[15px] leading-snug " + (final ? "text-zinc-100" : "italic text-zinc-400")}>
        {final ? tx.text_final : tx.text_partial || "…"}
        {!final && <span className="ml-1 inline-block size-2 animate-pulse rounded-full bg-red-500 align-middle" />}
      </p>
    </div>
  )
}

function Lane({
  title,
  sub,
  txs,
  state,
  onPlay,
}: {
  title: string
  sub: string
  txs: Transmission[]
  state: State
  onPlay: (tx: Transmission) => void
}) {
  const endRef = useRef<HTMLDivElement>(null)
  const last = txs[txs.length - 1]
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [txs.length, last?.text_partial, last?.text_final])
  return (
    <section className="flex min-h-0 flex-1 flex-col border-b border-border">
      <div className="flex items-baseline gap-2 bg-zinc-900 px-2 py-1">
        <h3 className="text-lg font-bold text-white">{title}</h3>
        <span className="text-sm text-zinc-400">{sub}</span>
        <span className="ml-auto text-xs text-zinc-500">{txs.length}</span>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {txs.map((tx) => (
          <TxRow key={tx.id} tx={tx} state={state} onPlay={onPlay} />
        ))}
        <div ref={endRef} />
      </ScrollArea>
    </section>
  )
}

export function ChannelLanes({
  state,
  audioCues,
  autoPlay,
}: {
  state: State
  audioCues: AudioCue[]
  autoPlay: boolean
}) {
  const audioRef = useRef<Partial<Record<Channel, HTMLAudioElement | null>>>({})
  const seen = useRef<number>(-1)

  const play = (ch: Channel, url: string) => {
    const lane: Channel = ch === "PTT" ? "TAC" : ch
    const el = audioRef.current[lane]
    if (!el) return
    el.src = url
    el.currentTime = 0
    void el.play().catch(() => {
      /* autoplay blocked until a user gesture */
    })
  }

  // audio_cue → play clip on its lane; only cues that arrive after mount, only when autoPlay.
  useEffect(() => {
    if (seen.current < 0) {
      seen.current = audioCues.length
      return
    }
    const fresh = audioCues.slice(seen.current)
    seen.current = audioCues.length
    if (!autoPlay) return
    for (const cue of fresh) if (cue.audio_url) play(cue.channel, cue.audio_url)
  }, [audioCues, autoPlay])

  const txs = [...state.transmissions].sort((a, b) => a.t_keyup - b.t_keyup)
  return (
    <div className="flex h-full min-h-0 flex-col">
      {LANES.map((l) => (
        <Lane
          key={l.ch}
          title={l.ko}
          sub={l.en}
          txs={txs.filter((t) => t.channel === l.ch || (l.also && t.channel === l.also))}
          state={state}
          onPlay={(tx) => tx.audio_url && play(tx.channel, tx.audio_url)}
        />
      ))}
      <audio ref={(el) => void (audioRef.current.CMD = el)} preload="none" />
      <audio ref={(el) => void (audioRef.current.TAC = el)} preload="none" />
    </div>
  )
}

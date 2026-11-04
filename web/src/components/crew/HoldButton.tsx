import { useEffect, useRef, useState, type PointerEvent } from "react"
import { cn } from "@/lib/utils"

const TONES = {
  red: "bg-red-600 text-white border-red-400",
  amber: "bg-amber-500 text-black border-amber-300",
  green: "bg-emerald-600 text-white border-emerald-400",
  blue: "bg-sky-600 text-white border-sky-400",
} as const

/** Hold-to-confirm button: fill bar over `holdMs`, fires onConfirm once; release early cancels. */
export default function HoldButton({
  label,
  sub,
  tone,
  holdMs = 800,
  disabled,
  onConfirm,
}: {
  label: string
  sub?: string
  tone: keyof typeof TONES
  holdMs?: number
  disabled?: boolean
  onConfirm: () => void | Promise<unknown>
}) {
  const [progress, setProgress] = useState(0)
  const [flash, setFlash] = useState(false)
  const raf = useRef<number | null>(null)
  const start = useRef(0)
  const fired = useRef(false)

  const cancel = () => {
    if (raf.current != null) cancelAnimationFrame(raf.current)
    raf.current = null
    if (!fired.current) setProgress(0)
  }

  useEffect(() => () => { if (raf.current != null) cancelAnimationFrame(raf.current) }, [])

  const begin = (e: PointerEvent<HTMLButtonElement>) => {
    if (disabled) return
    e.currentTarget.setPointerCapture?.(e.pointerId)
    fired.current = false
    start.current = performance.now()
    const step = () => {
      const p = Math.min(1, (performance.now() - start.current) / holdMs)
      setProgress(p)
      if (p >= 1) {
        fired.current = true
        raf.current = null
        setFlash(true)
        navigator.vibrate?.(60)
        void Promise.resolve(onConfirm()).catch((err) => console.error("hold action failed", err))
        window.setTimeout(() => { setFlash(false); setProgress(0) }, 600)
        return
      }
      raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
  }

  const holding = progress > 0 && progress < 1
  return (
    <button
      type="button"
      disabled={disabled}
      onPointerDown={begin}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onPointerCancel={cancel}
      onContextMenu={(e) => e.preventDefault()}
      className={cn(
        "relative w-full touch-none overflow-hidden rounded-2xl border-2 px-4 py-3 text-left select-none transition-transform duration-150",
        TONES[tone],
        holding && "scale-[0.97]",
        flash && "ring-4 ring-white",
        disabled && "opacity-40",
      )}
    >
      <span
        className="absolute inset-y-0 left-0 bg-white/30"
        style={{ width: `${progress * 100}%` }}
        aria-hidden
      />
      <span className="relative flex items-baseline justify-between gap-2">
        <span className="text-2xl font-bold tracking-tight">{label}</span>
        <span className="text-xs font-medium opacity-80">{flash ? "sent ✓" : sub ?? "hold"}</span>
      </span>
    </button>
  )
}

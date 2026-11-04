import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/** 390×844 device frame. `scale` shrinks it via CSS transform (and shrinks the layout box to match). */
export default function PhoneFrame({
  children,
  scale = 1,
  className,
}: {
  children: ReactNode
  scale?: number
  className?: string
}) {
  const W = 390
  const H = 844
  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: (W + 24) * scale, height: (H + 24) * scale }}
    >
      <div
        className="absolute top-0 left-0 rounded-[52px] border border-zinc-700 bg-zinc-900 p-3 shadow-2xl"
        style={{ width: W + 24, height: H + 24, transform: `scale(${scale})`, transformOrigin: "top left" }}
      >
        <div className="relative flex h-full w-full flex-col overflow-hidden rounded-[40px] bg-zinc-950 text-zinc-50">
          <div className="pointer-events-none absolute top-2 left-1/2 z-10 h-6 w-28 -translate-x-1/2 rounded-full bg-black" />
          {children}
        </div>
      </div>
    </div>
  )
}

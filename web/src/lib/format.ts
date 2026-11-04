import type { CardKind, Lang, Tag } from "./types"

export function fmtClock(t: number | null | undefined): string {
  if (t == null || !Number.isFinite(t)) return "–:––"
  const s = Math.max(0, Math.floor(t))
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, "0")}`
}

export function fmtLatency(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "–"
  return `${(ms / 1000).toFixed(1)} s`
}

type AnyTag = Tag | CardKind

const TAG_KO: Record<AnyTag, string> = {
  MAYDAY: "긴급탈출",
  DANGER: "위험",
  VICTIM_FOUND: "구조대상자",
  HELP_NEEDED: "지원요청",
  ROUTINE: "일반",
  RULE: "규칙",
}
const TAG_EN: Record<AnyTag, string> = {
  MAYDAY: "MAYDAY",
  DANGER: "DANGER",
  VICTIM_FOUND: "VICTIM FOUND",
  HELP_NEEDED: "HELP NEEDED",
  ROUTINE: "ROUTINE",
  RULE: "RULE",
}

export function tagLabel(tag: string, lang: Lang = "ko"): string {
  const k = tag as AnyTag
  return (lang === "ko" ? TAG_KO[k] : TAG_EN[k]) ?? tag
}

/** Tailwind classes for a tag chip (bg + text + border). */
export function tagColor(tag: string): string {
  switch (tag) {
    case "MAYDAY":
    case "RULE":
      return "bg-red-600 text-white border-red-400"
    case "DANGER":
      return "bg-amber-500 text-black border-amber-300"
    case "VICTIM_FOUND":
      return "bg-sky-500 text-black border-sky-300"
    case "HELP_NEEDED":
      return "bg-violet-500 text-white border-violet-300"
    default:
      return "bg-zinc-700 text-zinc-100 border-zinc-500"
  }
}

/** Border accent class for a tag. */
export function tagBorder(tag: string): string {
  switch (tag) {
    case "MAYDAY":
    case "RULE":
      return "border-red-500"
    case "DANGER":
      return "border-amber-400"
    case "VICTIM_FOUND":
      return "border-sky-400"
    case "HELP_NEEDED":
      return "border-violet-400"
    default:
      return "border-border"
  }
}

/** Look up a rule threshold (seconds) by any of several key spellings; falls back to the Settings default. */
export function threshold(th: Record<string, number> | undefined, keys: string[], fallback: number): number {
  if (th) for (const k of keys) if (typeof th[k] === "number") return th[k]
  return fallback
}
export const R1_KEYS = ["R1", "r1", "r1_ack_s"]
export const R1L2_KEYS = ["R1_level2", "r1_level2", "r1_level2_s"]
export const R2_KEYS = ["R2", "r2", "r2_silent_s"]

export function unitStatusColor(status: string): string {
  switch (status) {
    case "IN":
      return "bg-emerald-600 text-white"
    case "TRAPPED":
      return "bg-red-600 text-white"
    case "LOW_AIR":
      return "bg-amber-500 text-black"
    case "OK":
      return "bg-sky-600 text-white"
    case "OUT":
      return "bg-zinc-600 text-white"
    default:
      return "bg-zinc-800 text-zinc-200"
  }
}

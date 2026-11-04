export type Row = Record<string, unknown>

/** Pull the per-condition view of one line, tolerating the shapes run_eval.py may emit:
 *  {condition: "radio_kw", ...} rows, or one row per line with {conditions|results: {radio_kw: {...}}} / {radio_kw: {...}}. */
export function linesForCondition(lines: Row[], cond: string): Row[] {
  const out: Row[] = []
  for (const l of lines) {
    if (typeof l.condition === "string") {
      if (l.condition === cond) out.push(l)
      continue
    }
    const nested =
      (l.conditions as Record<string, Row> | undefined)?.[cond] ??
      (l.results as Record<string, Row> | undefined)?.[cond] ??
      (l[cond] as Row | undefined)
    if (nested && typeof nested === "object") out.push({ ...l, ...nested })
    else out.push(l)
  }
  return out
}

export function pick(r: Row, ...keys: string[]): unknown {
  for (const k of keys) {
    const parts = k.split(".")
    let v: unknown = r
    for (const p of parts) v = v && typeof v === "object" ? (v as Row)[p] : undefined
    if (v !== undefined && v !== null) return v
  }
  return undefined
}

export function show(v: unknown): string {
  if (v === undefined || v === null) return "—"
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2)
  if (typeof v === "boolean") return v ? "✓" : "✗"
  if (Array.isArray(v)) return v.join(", ")
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}

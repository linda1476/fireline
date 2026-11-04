import { useState } from "react"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { State, Unit, Zone } from "@/lib/types"

type Pt = [number, number]

function bbox(poly: number[][]) {
  const xs = poly.map((p) => p[0])
  const ys = poly.map((p) => p[1])
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) }
}
function centroid(poly: number[][]): Pt {
  if (!poly.length) return [0, 0]
  const b = bbox(poly)
  return [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2]
}

function maydayUnits(state: State): Set<string> {
  const s = new Set<string>()
  for (const c of state.cards)
    if (c.kind === "MAYDAY" && c.unit_id && (c.state === "open" || c.state === "escalated")) s.add(c.unit_id)
  for (const u of Object.values(state.units)) if (u.status === "TRAPPED") s.add(u.id)
  return s
}

const SEARCH_FILL: Record<string, string> = {
  none: "rgba(63,63,70,0.35)",
  primary: "rgba(16,185,129,0.22)",
  cross: "rgba(16,185,129,0.35)",
  searched: "rgba(16,185,129,0.5)",
}

function UnitMarkers({
  units,
  zones,
  flipY,
  mayday,
  size,
}: {
  units: Unit[]
  zones: Record<string, Zone>
  flipY: (y: number) => number
  mayday: Set<string>
  size: number
}) {
  const byZone: Record<string, Unit[]> = {}
  for (const u of units) if (u.zone_id && zones[u.zone_id]) (byZone[u.zone_id] ??= []).push(u)
  return (
    <>
      {Object.entries(byZone).flatMap(([zid, us]) => {
        const [cx, cy] = centroid(zones[zid].polygon)
        return us.map((u, i) => {
          const x = cx + (i - (us.length - 1) / 2) * size * 3.2
          const y = flipY(cy) + size * 1.2
          const red = mayday.has(u.id)
          return (
            <g key={u.id}>
              {red && (
                <circle cx={x} cy={y} r={size * 1.8} fill="none" stroke="#ef4444" strokeWidth={size * 0.25}>
                  <animate attributeName="r" values={`${size};${size * 2.6};${size}`} dur="1.2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="1;0.1;1" dur="1.2s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={x} cy={y} r={size} fill={red ? "#ef4444" : u.role === "RIT" ? "#a855f7" : "#22d3ee"} stroke="#000" strokeWidth={size * 0.15} />
              <text x={x} y={y + size * 2.4} textAnchor="middle" fontSize={size * 1.25} fill="#fff" fontWeight={700}>
                {u.name ?? u.callsign}
              </text>
            </g>
          )
        })
      })}
    </>
  )
}

function IndoorGrid({ state, floor }: { state: State; floor: number }) {
  const zones = Object.values(state.zones).filter((z) => z.kind === "indoor" && z.floor === floor)
  // parents first so children draw on top
  zones.sort((a, b) => (a.parent ? 1 : 0) - (b.parent ? 1 : 0))
  const all = zones.flatMap((z) => z.polygon)
  const b = all.length ? bbox(all) : { x0: 0, x1: 20, y0: 0, y1: 12 }
  const pad = 1.5
  const flipY = (y: number) => b.y1 - y + b.y0
  const vb = `${b.x0 - pad} ${b.y0 - pad} ${b.x1 - b.x0 + pad * 2} ${b.y1 - b.y0 + pad * 2 + 1.5}`
  const ids = new Set(zones.map((z) => z.id))
  const units = Object.values(state.units).filter((u) => u.zone_id && ids.has(u.zone_id))
  const mayday = maydayUnits(state)
  return (
    <svg viewBox={vb} className="h-full w-full" preserveAspectRatio="xMidYMid meet">
      {zones.map((z) => {
        const r = bbox(z.polygon)
        const hazard = z.hazards.length > 0
        const victims = z.victim_reports.reduce((n, v) => n + (v.count ?? 1), 0)
        return (
          <g key={z.id}>
            <rect
              x={r.x0}
              y={flipY(r.y1)}
              width={r.x1 - r.x0}
              height={r.y1 - r.y0}
              fill={hazard ? "rgba(245,158,11,0.35)" : SEARCH_FILL[z.search_state] ?? SEARCH_FILL.none}
              stroke={hazard ? "#f59e0b" : "#a1a1aa"}
              strokeWidth={z.parent ? 0.12 : 0.08}
              strokeDasharray={z.parent ? "0.4 0.2" : undefined}
            />
            <text x={r.x0 + 0.3} y={flipY(r.y1) + 0.9} fontSize={0.7} fill="#e4e4e7" fontWeight={600}>
              {z.label_ko}
            </text>
            <text x={r.x0 + 0.3} y={flipY(r.y1) + 1.6} fontSize={0.5} fill="#a1a1aa">
              {z.id} · {z.search_state}
            </text>
            {hazard && (
              <text x={r.x1 - 0.3} y={flipY(r.y1) + 0.9} fontSize={0.6} fill="#fbbf24" textAnchor="end">
                ⚠ {z.hazards[z.hazards.length - 1].text.slice(0, 14)}
              </text>
            )}
            {victims > 0 && (
              <g transform={`translate(${r.x1 - 1.2} ${flipY(r.y0) - 1.4})`}>
                <path d="M0 -0.9 a0.6 0.6 0 1 1 0.01 0 Z M0 0.4 L-0.5 -0.6 L0.5 -0.6 Z" fill="#38bdf8" />
                <text x={0.7} y={0.1} fontSize={0.8} fill="#38bdf8" fontWeight={700}>
                  {victims}
                </text>
              </g>
            )}
          </g>
        )
      })}
      <UnitMarkers units={units} zones={state.zones} flipY={flipY} mayday={mayday} size={0.45} />
      <text x={b.x0} y={b.y1 + pad + 0.6} fontSize={0.55} fill="#a1a1aa">
        front (Side Alpha) ↓ · amber = hazard · green = searched · pin = 구조대상자
      </text>
    </svg>
  )
}

function OutdoorSite({ state }: { state: State }) {
  const bld = state.building as {
    footprint?: number[][]
    footprint_m?: [number, number]
    height_m?: number
    collapse_ring?: { center?: number[]; radius_m?: number; label_ko?: string; label_en?: string }
    site?: { xmin: number; xmax: number; ymin: number; ymax: number }
  }
  const fp: number[][] =
    bld.footprint ??
    (bld.footprint_m ? [[0, 0], [bld.footprint_m[0], 0], [bld.footprint_m[0], bld.footprint_m[1]], [0, bld.footprint_m[1]]] : [[0, 0], [20, 0], [20, 12], [0, 12]])
  const fb = bbox(fp)
  const ring = bld.collapse_ring
  const rc: Pt = ring?.center ? [ring.center[0], ring.center[1]] : [(fb.x0 + fb.x1) / 2, (fb.y0 + fb.y1) / 2]
  const rr = ring?.radius_m ?? (bld.height_m ? bld.height_m * 1.5 : 18)
  const site = bld.site ?? { xmin: -16, xmax: 36, ymin: -14, ymax: 26 }
  const flipY = (y: number) => site.ymax - y + site.ymin
  const outdoor = Object.values(state.zones).filter((z) => z.kind === "outdoor")
  const ids = new Set(outdoor.map((z) => z.id))
  const units = Object.values(state.units).filter((u) => u.zone_id && ids.has(u.zone_id))
  const mayday = maydayUnits(state)
  return (
    <svg
      viewBox={`${site.xmin} ${site.ymin} ${site.xmax - site.xmin} ${site.ymax - site.ymin}`}
      className="h-full w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <circle cx={rc[0]} cy={flipY(rc[1])} r={rr} fill="rgba(239,68,68,0.06)" stroke="#ef4444" strokeWidth={0.25} strokeDasharray="1 0.6" />
      <text x={rc[0]} y={flipY(rc[1]) - rr - 0.6} fontSize={1.3} fill="#f87171" textAnchor="middle" fontWeight={700}>
        1.5H (SOP 205)
      </text>
      <rect x={fb.x0} y={flipY(fb.y1)} width={fb.x1 - fb.x0} height={fb.y1 - fb.y0} fill="#27272a" stroke="#e4e4e7" strokeWidth={0.2} />
      <text x={(fb.x0 + fb.x1) / 2} y={flipY((fb.y0 + fb.y1) / 2)} fontSize={1.2} fill="#d4d4d8" textAnchor="middle">
        {String((state.building as { kind_ko?: string }).kind_ko ?? "Building")}
      </text>
      {outdoor.map((z) => {
        const r = bbox(z.polygon)
        return (
          <g key={z.id}>
            <rect x={r.x0} y={flipY(r.y1)} width={r.x1 - r.x0} height={r.y1 - r.y0} fill="rgba(56,189,248,0.12)" stroke="#38bdf8" strokeWidth={0.15} />
            <text x={(r.x0 + r.x1) / 2} y={flipY(r.y0) + 1.3} fontSize={0.95} fill="#bae6fd" textAnchor="middle">
              {z.label_ko}
            </text>
          </g>
        )
      })}
      <UnitMarkers units={units} zones={state.zones} flipY={flipY} mayday={mayday} size={0.8} />
    </svg>
  )
}

const FLOORS: { v: string; label: string; floor: number }[] = [
  { v: "1", label: "1F", floor: 1 },
  { v: "2", label: "2F", floor: 2 },
  { v: "3", label: "3F", floor: 3 },
  { v: "4", label: "ROOF", floor: 4 },
]

export function MapTab({ state }: { state: State }) {
  const [view, setView] = useState<string>("2")
  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-2">
      <ToggleGroup
        value={[view]}
        onValueChange={(v: unknown[]) => {
          if (v.length) setView(String(v[v.length - 1]))
        }}
        variant="outline"
      >
        {FLOORS.map((f) => (
          <ToggleGroupItem key={f.v} value={f.v} className="px-3 text-base font-bold">
            {f.label}
          </ToggleGroupItem>
        ))}
        <ToggleGroupItem value="site" className="px-3 text-base font-bold">
          SITE
        </ToggleGroupItem>
      </ToggleGroup>
      <div className="min-h-0 flex-1 rounded-md border border-border bg-zinc-950">
        {view === "site" ? <OutdoorSite state={state} /> : <IndoorGrid state={state} floor={Number(view)} />}
      </div>
    </div>
  )
}

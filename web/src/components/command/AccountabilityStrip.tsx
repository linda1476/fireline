import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { fmtClock, R2_KEYS, threshold, unitStatusColor } from "@/lib/format"
import type { State } from "@/lib/types"

const ROLES = new Set(["CREW", "RIT", "EXTERIOR"])

export function AccountabilityStrip({ state }: { state: State }) {
  const r2 = threshold(state.thresholds, R2_KEYS, 60)
  const units = Object.values(state.units).filter((u) => ROLES.has(u.role))
  const maydayUnits = new Set(
    state.cards
      .filter((c) => c.kind === "MAYDAY" && (c.state === "open" || c.state === "escalated") && c.unit_id)
      .map((c) => c.unit_id as string),
  )
  return (
    <div className="bg-zinc-950">
      <Table className="text-[15px]">
        <TableHeader>
          <TableRow className="text-zinc-400">
            <TableHead>Unit</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Reported zone</TableHead>
            <TableHead>
              Last heard <span className="text-xs font-normal italic">(R2 {r2} s, demo timescale)</span>
            </TableHead>
            <TableHead>Pings</TableHead>
            <TableHead>Heard</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {units.map((u) => {
            const z = u.zone_id ? state.zones[u.zone_id] : undefined
            const age = u.last_heard_t != null ? state.t - u.last_heard_t : null
            const stale = u.interior && (age == null || age >= r2)
            const warn = u.interior && age != null && age >= r2 * 0.5
            const mayday = maydayUnits.has(u.id) || u.status === "TRAPPED"
            return (
              <TableRow key={u.id} className={mayday ? "bg-red-950/60" : ""}>
                <TableCell className="font-semibold text-white">
                  {u.callsign}
                  {u.name && <span className="ml-1.5 font-normal text-zinc-300">{u.name}</span>}
                  {mayday && <span className="ml-2 rounded bg-red-600 px-1 text-xs font-bold text-white">긴급탈출</span>}
                </TableCell>
                <TableCell className="text-zinc-400">{u.role}</TableCell>
                <TableCell>
                  <Badge className={unitStatusColor(u.status)}>{u.status}</Badge>
                </TableCell>
                <TableCell className="text-zinc-200">
                  {z ? z.label_ko : (u.zone_id ?? "—")}
                  {z && <span className="ml-1 text-xs text-zinc-500">{z.id}</span>}
                </TableCell>
                <TableCell
                  className={
                    "font-mono tabular-nums " + (stale ? "font-bold text-red-400" : warn ? "text-amber-300" : "text-zinc-200")
                  }
                >
                  {u.last_heard_t != null ? fmtClock(u.last_heard_t) : "—"}
                  {age != null && <span className="ml-2">({Math.floor(age)} s ago)</span>}
                </TableCell>
                <TableCell className={u.unanswered_pings > 0 ? "font-bold text-amber-300" : "text-zinc-500"}>
                  {u.unanswered_pings}
                </TableCell>
                <TableCell className="tabular-nums text-zinc-200">
                  heard {u.heard_count} of {u.total_count}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

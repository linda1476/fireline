import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { pick, show, type Row } from "./evalData"

export default function ResultsTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <p className="p-4 text-sm text-muted-foreground">No per-line rows.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>id</TableHead>
          <TableHead>lang</TableHead>
          <TableHead>expected</TableHead>
          <TableHead>predicted</TableHead>
          <TableHead>unit raw / snapped</TableHead>
          <TableHead>floor</TableHead>
          <TableHead>terms hit</TableHead>
          <TableHead>evidence</TableHead>
          <TableHead className="text-right">ASR ms</TableHead>
          <TableHead className="text-right">Spark ms</TableHead>
          <TableHead>transcript</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => {
          const exp = pick(r, "expect.tag", "expected_tag", "expected", "label")
          const pred = pick(r, "triage.tag", "pred_tag", "predicted", "tag")
          const ok = exp !== undefined && pred !== undefined ? exp === pred : undefined
          return (
            <TableRow key={`${show(pick(r, "id", "line_id"))}-${i}`}>
              <TableCell className="font-mono text-xs">{show(pick(r, "id", "line_id"))}</TableCell>
              <TableCell>{show(pick(r, "lang"))}</TableCell>
              <TableCell>{show(exp)}</TableCell>
              <TableCell className={cn(ok === false && "font-bold text-destructive", ok && "text-emerald-600")}>
                {show(pred)}
              </TableCell>
              <TableCell className="text-xs">
                {show(pick(r, "unit_raw", "triage.speaker_unit"))} / {show(pick(r, "unit_snapped", "speaker_unit_snapped"))}
              </TableCell>
              <TableCell>{show(pick(r, "floor_match", "floor", "triage.location.floor"))}</TableCell>
              <TableCell className="text-xs">{show(pick(r, "critical_hits", "terms_hit", "critical_term_hit"))}</TableCell>
              <TableCell>{show(pick(r, "evidence_verified", "evidence_ok"))}</TableCell>
              <TableCell className="text-right tabular-nums">{show(pick(r, "asr_ms", "latency.asr_ms"))}</TableCell>
              <TableCell className="text-right tabular-nums">{show(pick(r, "triage_ms", "spark_ms", "latency.triage_ms"))}</TableCell>
              <TableCell className="max-w-[28rem] truncate text-xs" title={show(pick(r, "transcript", "text"))}>
                {show(pick(r, "transcript", "text"))}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}


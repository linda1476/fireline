import { useEffect, useState } from "react"
import { Link } from "react-router"
import * as api from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import ResultsTable from "@/components/eval/ResultsTable"
import { linesForCondition, pick, show, type Row } from "@/components/eval/evalData"

const CONDITIONS = ["clean_kw", "clean_nokw", "radio_kw", "radio_nokw"] as const

// [label, candidate keys in results.json (first present wins), kind]
const METRICS: [string, string[], "pct" | "ms" | "raw"][] = [
  ["MAYDAY recall", ["mayday_recall", "mayday.recall"], "pct"],
  ["MAYDAY FP", ["mayday_fp", "mayday_false_positives", "mayday.fp"], "raw"],
  ["5-way accuracy", ["accuracy", "acc_5way", "tag_accuracy"], "pct"],
  ["macro-F1", ["macro_f1", "f1_macro"], "pct"],
  ["critical-term hit rate", ["critical_term_hit_rate", "critical_hit_rate", "term_hit_rate"], "pct"],
  ["unit match (raw)", ["unit_raw_exact", "unit_match_raw", "unit_raw", "unit.raw"], "pct"],
  ["unit match (snapped)", ["unit_snapped_exact", "unit_match_snapped", "unit_snapped", "unit.snapped"], "pct"],
  ["floor match", ["floor_match", "floor_exact"], "pct"],
  ["codeword-masked recall", ["codeword_masked_recall", "codeword_recall", "masked_recall"], "raw"],
  ["evidence verbatim rate", ["evidence_verbatim_rate", "evidence_rate", "evidence_verified_rate"], "pct"],
  ["Spark p50", ["spark_p50_ms", "spark_ms_p50", "triage_ms_p50", "spark.p50", "latency.spark_p50"], "ms"],
  ["Spark p95", ["spark_p95_ms", "spark_ms_p95", "triage_ms_p95", "spark.p95", "latency.spark_p95"], "ms"],
  ["ASR p50", ["asr_p50_ms", "asr_ms_p50", "asr.p50", "latency.asr_p50"], "ms"],
  ["ASR p95", ["asr_p95_ms", "asr_ms_p95", "asr.p95", "latency.asr_p95"], "ms"],
]

function fmt(v: unknown, kind: "pct" | "ms" | "raw"): string {
  if (typeof v === "number") {
    if (kind === "pct" && v <= 1) return `${(v * 100).toFixed(0)}%`
    if (kind === "ms") return `${Math.round(v)} ms`
  }
  return show(v)
}

type Results = { meta?: Row; conditions?: Record<string, Row>; lines?: Row[]; gate?: unknown }

export default function Eval() {
  const [data, setData] = useState<Results | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    Promise.resolve(api.getEvalResults())
      .then((r: unknown) => {
        const res = r as Results | null
        if (!res || !res.conditions || Object.keys(res.conditions).length === 0) setErr("eval not run yet")
        else setData(res)
      })
      .catch(() => setErr("eval not run yet"))
  }, [])

  const conds = data?.conditions ? CONDITIONS.filter((c) => data.conditions?.[c]) : []
  const meta = data?.meta ?? {}
  const gateRaw = pick(meta, "gate", "gate_verdict") ?? data?.gate
  const radioRecall = pick(data?.conditions?.radio_kw ?? {}, "mayday_recall", "mayday.recall")
  const gatePass =
    typeof gateRaw === "boolean"
      ? gateRaw
      : typeof gateRaw === "object" && gateRaw !== null && "pass" in gateRaw
        ? Boolean((gateRaw as { pass: unknown }).pass)
        : typeof gateRaw === "string"
          ? /pass/i.test(gateRaw)
          : typeof radioRecall === "number"
            ? radioRecall >= 0.8
            : undefined

  return (
    <div className="min-h-svh bg-background p-6 text-foreground">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-xs text-muted-foreground hover:text-foreground">
            ← back
          </Link>
          <h1 className="text-xl font-bold">Eval</h1>
          {gatePass !== undefined && (
            <Badge variant={gatePass ? "default" : "destructive"}>
              GATE {gatePass ? "PASS" : "FAIL"} · radio-KO MAYDAY recall{" "}
              {typeof radioRecall === "number" ? `${(radioRecall * 100).toFixed(0)}%` : "?"} (≥ 80%)
            </Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          synthetic Gemini-TTS speech + codec degradation, n = {show(pick(meta, "n", "n_lines") ?? 36)}
          {pick(meta, "timestamp", "date", "run_at") !== undefined && ` · ${show(pick(meta, "timestamp", "date", "run_at"))}`}
          {typeof gateRaw === "string" && ` · ${gateRaw}`}
        </p>

        {err && <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">{err}</div>}

        {data && (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>metric</TableHead>
                  {conds.map((c) => (
                    <TableHead key={c} className="text-right font-mono">
                      {c}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {METRICS.map(([label, keys, kind]) => (
                  <TableRow key={label}>
                    <TableCell className="font-medium">{label}</TableCell>
                    {conds.map((c) => (
                      <TableCell key={c} className="text-right tabular-nums">
                        {fmt(pick(data.conditions?.[c] ?? {}, ...keys), kind)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {conds.length > 0 && (
              <Tabs defaultValue={conds.includes("radio_kw") ? "radio_kw" : conds[0]}>
                <TabsList>
                  {conds.map((c) => (
                    <TabsTrigger key={c} value={c} className="font-mono">
                      {c}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {conds.map((c) => (
                  <TabsContent key={c} value={c}>
                    <ResultsTable rows={linesForCondition(data.lines ?? [], c)} />
                  </TabsContent>
                ))}
              </Tabs>
            )}
          </>
        )}
      </div>
    </div>
  )
}

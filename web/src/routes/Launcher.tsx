import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  getScenarioLines,
  listRuns,
  promoteRun,
  resetScenario,
  startScenario,
  stopScenario,
  type ScenarioLine,
} from "@/lib/api"
import { fmtClock } from "@/lib/format"
import type { Lang, Mode, RunInfo, ScenarioStartBody, State } from "@/lib/types"
import { applyLocal, useEarshot } from "@/lib/ws"

function Choice<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { v: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 text-sm text-zinc-400">{label}</span>
      <ToggleGroup
        value={[value]}
        onValueChange={(v: unknown[]) => {
          // single-select: the newest pressed value wins; un-pressing the current one keeps it
          if (v.length) onChange(String(v[v.length - 1]) as T)
        }}
        variant="outline"
      >
        {options.map((o) => (
          <ToggleGroupItem
            key={o.v}
            value={o.v}
            className="px-4 text-base font-semibold text-zinc-400 aria-pressed:bg-zinc-100 aria-pressed:text-zinc-950 data-[pressed]:bg-zinc-100 data-[pressed]:text-zinc-950"
          >
            {o.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}

export default function Launcher() {
  const { state, connected, sample } = useEarshot()
  const [mode, setMode] = useState<Mode>("LIVE")
  const [audio, setAudio] = useState<"radio" | "clean">("radio")
  const [lang, setLang] = useState<Lang>("ko")
  const [run, setRun] = useState("best")
  const [lines, setLines] = useState<ScenarioLine[]>([])
  const [runs, setRuns] = useState<RunInfo[]>([])
  const [busy, setBusy] = useState(false)

  const refreshRuns = useCallback(() => {
    if (sample) return
    listRuns()
      .then((r) => setRuns(Array.isArray(r) ? r : []))
      .catch(() => setRuns([]))
  }, [sample])

  useEffect(() => {
    if (sample) return
    getScenarioLines()
      .then(setLines)
      .catch(() => setLines([]))
    refreshRuns()
  }, [sample, refreshRuns])

  // the exact body the Run button sends (shown under the button)
  const body: ScenarioStartBody =
    mode === "LIVE" ? { mode: "LIVE", scenario: "hanbit", lang, audio } : { mode: "REPLAY", run: run.trim() || "best" }
  const bodyLabel =
    body.mode === "LIVE" ? `LIVE · ${audio} · ${lang === "ko" ? "한국어" : "English"}` : `REPLAY · ${body.run}`
  // GET /api/runs is newest first; "last run" = newest recorded run_*.jsonl (not best.jsonl itself)
  const lastRun = runs.find((r) => r.file !== "best.jsonl" && r.file.startsWith("run_"))

  const call = async (label: string, p: () => Promise<State>, okMsg = label) => {
    setBusy(true)
    try {
      applyLocal({ type: "snapshot", payload: await p() })
      toast.success(okMsg)
    } catch (e) {
      toast.error(`${label} failed`, { description: String(e) })
    } finally {
      setBusy(false)
    }
  }

  const promote = async (file: string) => {
    setBusy(true)
    try {
      const r = await promoteRun(file)
      toast.success(`Promoted ${r?.promoted ?? file} → best`)
      refreshRuns()
    } catch (e) {
      toast.error("Promote failed", { description: String(e) })
    } finally {
      setBusy(false)
    }
  }

  const links = [
    { to: "/command", label: "Command (IC)" },
    { to: "/crew/kim", label: "Crew · 김하늘 (kim)" },
    { to: "/crew/park", label: "Crew · 박준 (park)" },
    { to: "/demo", label: "Demo split" },
    { to: "/eval", label: "Eval" },
  ]
  const qs = sample ? "?sample=1" : ""

  return (
    <div className="min-h-screen bg-background px-6 py-8 text-foreground">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="flex flex-wrap items-center gap-3">
          <h1 className="text-4xl font-black tracking-tight">Earshot</h1>
          <span className="text-lg text-zinc-400">radio triage for the incident commander</span>
          <span className="ml-auto flex items-center gap-2 text-sm">
            <span className={"size-2.5 rounded-full " + (sample ? "bg-amber-400" : connected ? "bg-emerald-500" : "bg-red-500")} />
            {sample ? "sample data" : connected ? "backend connected" : "backend offline"}
          </span>
          {state && (
            <Badge className={"h-7 px-2 text-base font-bold " + (state.mode === "LIVE" ? "bg-red-600 text-white" : "bg-sky-600 text-white")}>
              {state.mode}
            </Badge>
          )}
        </header>

        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">한빛 도장공장 화재 · Hanbit paint factory fire</CardTitle>
            <CardDescription className="text-base">
              3-storey steel-frame paint factory · 2 radio channels (지휘망 CMD / 작전망 TAC) · 6 units · 긴급탈출 at ~1:18
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Choice label="Mode" value={mode} onChange={setMode} options={[{ v: "LIVE", label: "LIVE" }, { v: "REPLAY", label: "REPLAY" }]} />
            {mode === "REPLAY" ? (
              <div className="flex items-center gap-3">
                <span className="w-20 text-sm text-zinc-400">Run</span>
                <input
                  className="h-9 w-72 rounded-md border border-input bg-transparent px-2 text-base"
                  value={run}
                  onChange={(e) => setRun(e.target.value)}
                  placeholder="best"
                  list="earshot-runs"
                />
                <datalist id="earshot-runs">
                  <option value="best" />
                  {runs.map((r) => (
                    <option key={r.file} value={r.file} />
                  ))}
                </datalist>
                <span className="text-xs text-zinc-500">recorded LIVE run (data/cache/*.jsonl)</span>
              </div>
            ) : (
              <>
                <Choice label="Audio" value={audio} onChange={setAudio} options={[{ v: "radio", label: "radio" }, { v: "clean", label: "clean" }]} />
                <Choice label="Language" value={lang} onChange={setLang} options={[{ v: "ko", label: "한국어 ko" }, { v: "en", label: "English en" }]} />
              </>
            )}
            <div className="flex flex-wrap gap-3 pt-2">
              <Button
                size="lg"
                className={
                  "h-11 px-6 text-lg font-bold text-white " +
                  (mode === "LIVE" ? "bg-red-600 hover:bg-red-500" : "bg-sky-600 hover:bg-sky-500")
                }
                disabled={busy}
                onClick={() =>
                  call("Run", () => startScenario(body), body.mode === "LIVE" ? "LIVE run started" : `REPLAY started · ${body.run}`)
                }
              >
                Run {mode}
              </Button>
              <Button size="lg" variant="outline" className="h-11 px-6 text-lg" disabled={busy} onClick={() => call("Stop", stopScenario)}>
                Stop
              </Button>
              <Button size="lg" variant="ghost" className="h-11 px-6 text-lg" disabled={busy} onClick={() => call("Reset", resetScenario)}>
                Reset
              </Button>
              {state && (
                <span className="self-center font-mono text-2xl tabular-nums">
                  {fmtClock(state.t)} {state.running ? "▶" : "■"}
                </span>
              )}
            </div>
            <div className="text-sm text-zinc-300">
              will send{" "}
              <b className={"font-mono " + (mode === "LIVE" ? "text-red-400" : "text-sky-400")}>{bodyLabel}</b>
              <span className="ml-2 font-mono text-xs text-zinc-500">{JSON.stringify(body)}</span>
            </div>
          </CardContent>
        </Card>

        <nav className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to + qs}
              className="rounded-lg border border-border bg-zinc-900 px-3 py-4 text-center text-base font-semibold hover:bg-zinc-800"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        {!sample && (
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-center gap-3">
              <CardTitle>Recorded runs ({runs.length})</CardTitle>
              <Button
                size="sm"
                className="ml-auto bg-amber-500 font-bold text-black hover:bg-amber-400"
                disabled={busy || !lastRun}
                title={lastRun ? `copy ${lastRun.file} → best.jsonl` : "no run_*.jsonl yet"}
                onClick={() => {
                  if (lastRun) void promote(lastRun.file)
                }}
              >
                Promote last run → best
              </Button>
              <Button size="sm" variant="ghost" onClick={refreshRuns}>
                Refresh
              </Button>
            </CardHeader>
            <CardContent className="max-h-64 space-y-1 overflow-auto text-sm">
              {runs.length === 0 && <p className="text-zinc-500">no recorded runs</p>}
              {runs.map((r) => (
                <div key={r.file} className="flex items-center gap-3">
                  <span className="min-w-0 flex-1 truncate font-mono">{r.file}</span>
                  {r.best && <span className="rounded bg-amber-500 px-1.5 text-xs font-bold text-black">best</span>}
                  <span className="w-16 text-right font-mono text-zinc-400">
                    {typeof r.t_max === "number" ? fmtClock(r.t_max) : "—"}
                  </span>
                  <span className="w-20 text-right font-mono text-zinc-500">{Math.round((r.size ?? 0) / 1024)} KB</span>
                  {r.file.startsWith("run_") ? (
                    <Button size="xs" variant="outline" disabled={busy} onClick={() => void promote(r.file)}>
                      promote
                    </Button>
                  ) : (
                    <span className="w-[62px]" />
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {lines.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Scenario lines ({lines.length})</CardTitle>
            </CardHeader>
            <CardContent className="max-h-80 space-y-1 overflow-auto text-sm">
              {lines.map((l) => (
                <div key={l.id} className="flex gap-2">
                  <span className="w-10 shrink-0 font-mono text-zinc-500">{l.id}</span>
                  <span className="w-12 shrink-0 font-mono text-zinc-500">{typeof l.t === "number" ? fmtClock(l.t) : ""}</span>
                  <span className="w-12 shrink-0 text-zinc-400">{l.channel ?? ""}</span>
                  <span>{String(l.text_ko ?? l.text ?? "")}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

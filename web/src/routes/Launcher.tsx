import { useEffect, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { getScenarioLines, resetScenario, startScenario, stopScenario, type ScenarioLine } from "@/lib/api"
import { fmtClock } from "@/lib/format"
import type { Lang, Mode, State } from "@/lib/types"
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
          if (v.length) onChange(String(v[v.length - 1]) as T)
        }}
        variant="outline"
      >
        {options.map((o) => (
          <ToggleGroupItem key={o.v} value={o.v} className="px-4 text-base font-semibold">
            {o.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}

export default function Launcher() {
  const { state, connected, sample } = useEarshot()
  const [mode, setMode] = useState<Mode>("REPLAY")
  const [audio, setAudio] = useState<"radio" | "clean">("radio")
  const [lang, setLang] = useState<Lang>("ko")
  const [run, setRun] = useState("best")
  const [lines, setLines] = useState<ScenarioLine[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (sample) return
    getScenarioLines()
      .then(setLines)
      .catch(() => setLines([]))
  }, [sample])

  const call = async (label: string, p: () => Promise<State>) => {
    setBusy(true)
    try {
      applyLocal({ type: "snapshot", payload: await p() })
      toast.success(label)
    } catch (e) {
      toast.error(`${label} failed`, { description: String(e) })
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
            {mode === "REPLAY" && (
              <div className="flex items-center gap-3">
                <span className="w-20 text-sm text-zinc-400">Run</span>
                <input
                  className="h-9 w-64 rounded-md border border-input bg-transparent px-2 text-base"
                  value={run}
                  onChange={(e) => setRun(e.target.value)}
                  placeholder="best"
                />
                <span className="text-xs text-zinc-500">recorded LIVE run (data/cache/*.jsonl)</span>
              </div>
            )}
            <Choice label="Audio" value={audio} onChange={setAudio} options={[{ v: "radio", label: "radio" }, { v: "clean", label: "clean" }]} />
            <Choice label="Language" value={lang} onChange={setLang} options={[{ v: "ko", label: "한국어 ko" }, { v: "en", label: "English en" }]} />
            <div className="flex flex-wrap gap-3 pt-2">
              <Button
                size="lg"
                className="h-11 bg-red-600 px-6 text-lg font-bold text-white hover:bg-red-500"
                disabled={busy}
                onClick={() => call("Run", () => startScenario({ mode, lang, audio, run: mode === "REPLAY" ? run || "best" : undefined }))}
              >
                Run
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

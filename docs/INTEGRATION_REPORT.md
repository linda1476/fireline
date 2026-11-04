# Earshot integration report (2026-11-04)

Integrator run against the real Meta API (Spark `muse-spark-1.3` with reasoning_effort=minimal, and realtime ASR). The audio is the clean TTS set.

## Exit criteria

| # | criterion | result |
|---|---|---|
| 1 | `uv run pytest -q` | PASS: 53 passed. Added `tests/conftest.py`, which puts the repo root on sys.path and registers the `network` marker. |
| 2 | `python -m server.cli replay --audio clean --speed 3` | PASS: 11 events in realtime ASR mode, L08 classed MAYDAY (kim / 2F-E-STORE / floor 2). The CLI does not run PTT, so L06 only shows as a cue line. |
| 3 | `python -m eval.run_eval --conditions clean_kw --only L08,K07,K10,M01,E07` | PASS after a fix (see below). n=5, 0 errors, MAYDAY recall 1.00, FP 0, 5-way acc 1.00, unit snapped 1.00, floor 1.00, codeword-masked 2/2, Spark p50/p95 4144/5673 ms, ASR (file) p50/p95 3319/4249 ms. |
| 4 | Server LIVE run, then ack, stop, run file, REPLAY | PASS. A DANGER card after L04, VICTIM_FOUND after the L06 PTT, MAYDAY after L08 (escalated to level 2), and an R2 RULE card for Park at about t=144 that L13 resolved ("found OK"). There were 19 briefs, 1 R3 proposal, 46 trace entries and 7 agent wakes. `POST /api/cards/card_0004/ack` returned 200 → acked. The run file `data/cache/run_20261104_185255.jsonl` is 148 kB. REPLAY of that file re-emitted the run: 2 transmissions at t=19.5, matching the live timeline. |
| 5 | `cd web; npm run build` | PASS. No placeholder routes. A field-level drift script (pydantic `model_fields` against the TS interfaces) found no field drift. Added the `toast` WS message type, which the server sends during REPLAY, to `lib/types.ts`, and `lib/ws.ts` now shows it as a sonner toast. |
| 6 | This report | done |

## Fixes made during integration
- `tests/conftest.py` (new): fixes `ModuleNotFoundError: server` under bare `uv run pytest` and registers the `network` marker.
- `eval/run_eval.py` `snap_unit()`: the eval passed `roster` in the `lang` position of `verify.snap_unit(raw, lang, roster)`, so 4 of 5 lines raised `AttributeError` and unit and floor scored 0. It now calls the function by its real signature.
- `server/triage.py` prompt: added a rule that IC → dispatch requests for apparatus or a higher alarm are ROUTINE. L05 and L09 had come back as HELP_NEEDED. A re-check of L05 on its own now gives ROUTINE. The server run had started before this edit and still classed L09 as HELP_NEEDED, so this fix is not verified end-to-end.
- `server/config.py`: `agent_timeout_s` default changed from 8 to 12 s. In the LIVE run, 5 of 7 agent wakes hit `timeout` and went to the router fallback (see the trace `fallback` entries in the run file). The change has not been re-run.
- `web/src/lib/types.ts`, `web/src/lib/ws.ts`: added the `toast` WS type.

## Measured latencies (server LIVE run, clean audio, 1x)

`total_ms` runs from key-up to Event, so it includes the clip's own length.

| event | line | tag | asr_ms | triage_ms | total_ms |
|---|---|---|---|---|---|
| evt_0001 | L01 | ROUTINE | 568 | 5938 | 21097 |
| evt_0002 | L02 | ROUTINE | 531 | 2981 | 12000 |
| evt_0003 | L03 | ROUTINE | 308 | 3026 | 10862 |
| evt_0004 | L04 | DANGER | 257 | 3304 | 17088 |
| evt_0005 | L05 | ROUTINE | 307 | 3881 | 10727 |
| evt_0006 | L06 (PTT) | VICTIM_FOUND | 258 | 1938 | 8535 |
| evt_0007 | L07 | ROUTINE | 458 | 2414 | 9160 |
| evt_0008 | L09 | HELP_NEEDED (label ROUTINE) | 368 | 3315 | 9340 |
| evt_0009 | L08 | MAYDAY | 319 | 3982 | 13907 |
| evt_0010 | L10 | HELP_NEEDED | 259 | 2335 | 6954 |
| evt_0011 | L11 | MAYDAY | 202 | 5070 | 18873 |
| evt_0012 | L13 | ROUTINE | 472 | 3643 | 11844 |

Realtime ASR end-of-speech → final: 200–570 ms. Spark triage: 1.9–5.9 s. Agent wake: often over 8 s.

## What works
- Realtime ENDPOINTING on CMD and TAC with turn merging, then the gate, triage, verify/snap, Event, World, cards, rules and WS.
- The PTT socket path (L06 → VICTIM_FOUND kim/2F-E-OFFICE).
- Rule behaviour seen in the LIVE run:
  - R1 escalations: MAYDAY reached level 2 and RULE level 1.
  - R2 ping ×3 → RULE card, resolved when L13 came in.
  - R3 proposal on DANGER while the strategy was OFFENSIVE.
  - HELP_NEEDED was escalated to level 1 by t=148. R5 is assumed to be the cause; this was not traced.
- The L11 IC broadcast deduped into Kim's MAYDAY card.
- The relevance agent sent P1/P0 briefs and holds, with a fallback to the router on timeout. There were 0 checker rejections.
- The run recorder and REPLAY at 1x. Eval with a partial-run results.json and results.md.

## Stubbed / untested
- `cache.memo` is not wired into `server/triage.py` (TODO there), and the eval uses its own `eval/.memo.jsonl`.
- No run has been copied to `data/cache/best.jsonl`, so `REPLAY run:"best"` will 404 until someone copies a good run there.
- Not run: radio audio over realtime, `lang=en` in LIVE, and the full 144-call eval matrix.
- No browser render of any screen was checked: Command, Crew and Demo were only built, not opened.
- The agent's re-check at a 12 s timeout has not been run.

## Top 5 remaining bugs
1. **Agent timeout / fallback rate.** `server/config.py:38`: with an 8 s limit, 5 of 7 wakes timed out and every MAYDAY brief came from the router fallback. The limit is raised to 12 s but not re-measured. If it still times out, cut the wake to one round or use a smaller snapshot (`server/agent.py`).
2. **MAYDAY escalates to level 2 almost at once.** `server/rules.py:99` R1 counts from `card.created_t`, and `server/world.py:322` sets that to `ev.t` (key-up, 78). The card only exists about 14 s later (total_ms 13907), so it shows up already at level 2. R1 should count from the wall time the card was created, or from `Event.t + total_ms/1000`.
3. **P0 brief sent to the unit in distress.** The L11 broadcast (evt_0011, speaker ic) pushed a P0 brief "김하늘 … 긴급탈출 발생" to kim himself. `server/router_fallback.py` and `server/agent.py` skip only the speaking unit, not the unit named in `distress.who` or the card's `unit_id`.
4. **`verify.snap_unit` signature differs from CONTRACT.** `server/verify.py:68` is `(raw, lang, roster: dict)`, while CONTRACT says `(raw, roster, lang)`. The eval was broken by this; other callers may be too. Make CONTRACT and the code agree.
5. **English ASR keyword over 30 characters.** `data/keywords.json:10` contains "personnel accountability report" (31 characters), which the API rejects with a 400. LIVE with `lang=en` will fail ASR. Only the eval filters it out (`asr_keywords()`).

Other issues:
- L04 snaps to zone 2F-E / floor 2, while the label says 3F (`server/verify.py` snap_zone prefers the longest alias, and the text mentions both floors).
- LIVE `/api/scenario/start` ignores `speed` (`server/main.py:400`).
- REST acks sent after the scenario ends are not recorded, because the recorder closes when `running` turns false (`server/main.py:283`).

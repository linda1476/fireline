# VERIFY_RUN2: second LIVE run, checked after the live-run fixes

- **Run file:** `data/cache/run_20261104_195929.jsonl` (LIVE, hanbit, ko, radio). It was not promoted.
- **Driven by:** REST on a private server on :8001. Ports 8000 and 5173 were not touched.
- **Checker:** `uv run python scripts/check_run.py data/cache/run_20261104_195929.jsonl [state.json] --tables`. It folds the run file into a state and keeps every version of each card, so "never escalated" is checked across the whole history.
- **IC actions:** at t=107.8 the MAYDAY `card_0003` was acked, and `prop_0002` (RIT_DEPLOY) and `prop_0003` (RADIO_SILENCE) were approved.
- **Builds:** `uv run python -m pytest -q` → 97 passed. `npm run build` → built, with only the chunk-size warning.
- **`running`:** POST /api/scenario/start returned `running: true`. Every poll showed `running=True` until the end of the run, at t=167.2.

## Checks: 14/15 PASS

| # | Check | Result | Evidence |
|---|---|---|---|
| a1 | DANGER card | PASS | `card_0001` (L04) |
| a2 | VICTIM_FOUND card, never escalated | PASS | `card_0002` stayed open in every recorded version. No escalate_to_ic call was made on its event. |
| a3 | MAYDAY who/what/where/needs filled | PASS | `card_0003`: 한빛구조대 김하늘 / 대원고립 / 2층 동쪽 창고 / 사다리랑 공기용기 필요. Air was also filled: "공기 얼마 안 남았다". |
| a4 | R2 RULE resolved "found OK" | PASS | `card_0004` resolved, note `found OK (L13)`, at t≈168.7. See note 1. |
| b1 | no checker "unknown unit_id None" | PASS | 0 found. The whole run had 0 checker rejections. |
| b2 | no tool_call with empty args | PASS | 0 found. No truncation retry was needed: every response came back complete. |
| c | ask kim "needs" ≤ 10 s after the MAYDAY card | PASS | Sent by the **rule** (R6) at +6.7 s with the text "필요한 것이 무엇입니까? 사다리, 공기용기 등". The agent made the same `request_missing_field(kim, needs)` call in the same tick (+6.7 s), and it was deduped. |
| d1 | RIT_DEPLOY proposed + approved | PASS | Proposed by the **agent** (`prop_0002`) at +6.7 s after the MAYDAY card: "신속동료구조팀 2층 동쪽 창고 투입 (동측 창문)". Approved at t=107.8. |
| d2 | RADIO_SILENCE proposed + approved | PASS | Proposed by the **agent** (`prop_0003`) at +6.7 s: "전 출동대 무선 침묵, 긴급탈출 관련 교신만", to [hanbit_center, park, rit]. Approved at t=107.8. |
| d3 | rit.zone_id east after the RIT approval | PASS | `rit.zone_id = 2F-E-STORE`, assignment "RIT deploy 2F-E-STORE" |
| d4 | kim got the "구조대 투입 중" P0 | PASS | `brief_0009` P0 at t=108.1: "구조대 투입 중, 위치 유지." |
| e | fallback_routes ≤ 2 | **FAIL** | fallback_routes=4 out of agent_wakes=8; checker_rejections=0. See note 2. |
| f | every Event 500 ≤ after_speech_ms ≤ 15000 | PASS | 12 events, ranging from 2904 to 6386 ms |
| g1 | park heard ≥ 2, total ≥ 10 | PASS | heard_count=4, total_count=14 |
| g2 | kim got the DANGER brief (push, evidence L04) | PASS | `brief_0001`, from the agent: "2층 동측 도장공장에 신나 드럼 다수 등 인화물질 확인. 천장으로 연소 확대 우려, 퇴로 확보." |

**Defects (1)–(8) from run 1, against this run:**

| # | Defect | Status in this run |
|---|---|---|
| 1 | Empty-arg calls | Fixed: none, and the MAYDAY wake made 5 good calls in round 1 at 6.7 s. |
| 2 | RIT_DEPLOY / RADIO_SILENCE never proposed | Fixed: both were proposed by the agent. |
| 3 | Victim card escalated | Fixed. |
| 4 | Badge latency | Fixed at the data level: `after_speech_ms` is present. The UI was not checked. |
| 5 | Ask text | Fixed: the text names the field. The phone UI was not checked. |
| 6 | `running` flag | Fixed server-side. |
| 7, 8 | Launcher REPLAY default; UI_NOTES items 3–5 | Frontend only, not exercised here. |

## Per-event latency

`clip_s` = `t_end − t_keyup`. `after_speech_ms` = `total_ms − clip`.

| event | line | tag | src | asr_ms | triage_ms | after_speech_ms | total_ms | clip_s |
|---|---|---|---|---:|---:|---:|---:|---:|
| evt_0001 | L01 | ROUTINE | replay | 50 | 4427 | 4463 | 19343 | 14.9 |
| evt_0002 | L02 | ROUTINE | replay | 169 | 2747 | 2904 | 11664 | 8.8 |
| evt_0003 | L03 | ROUTINE | replay | 72 | 2954 | 3024 | 10824 | 7.8 |
| evt_0004 | L04 | DANGER | replay | 1597 | 4792 | 6386 | 20186 | 13.8 |
| evt_0005 | L05 | ROUTINE | replay | 1548 | 3578 | 5123 | 11923 | 6.8 |
| evt_0006 | L06 | VICTIM_FOUND | ptt | 237 | 3350 | 3614 | 10008 | 5.6 |
| evt_0007 | L07 | ROUTINE | replay | 1463 | 3167 | 4626 | 11186 | 6.6 |
| evt_0009 | L08 | MAYDAY | replay | 70 | 4102 | 4166 | 14046 | 9.9 |
| evt_0008 | L09 | ROUTINE | replay | 1559 | 4567 | 6125 | 12045 | 5.9 |
| evt_0010 | L10 | HELP_NEEDED | replay | 110 | 5954 | 6060 | 10700 | 4.6 |
| evt_0011 | L11 | MAYDAY | replay | 94 | 5693 | 5773 | 19653 | 13.9 |
| evt_0012 | L13 | ROUTINE | replay | 1543 | 4189 | 5732 | 13732 | 8.0 |

The MAYDAY badge now reads 4.2 s after end of transmission. Run 1 showed 14.8 s after key-up.

## Agent wakes

- **First tool call:** time from the round-1 wake trace to the first `tool_call` trace, on the scenario clock. For wake_0004, the agent's own `first_call_ms` is 12067, just past the 12 s timeout.
- **Late:** calls applied after the 12 s timeout.

| wake | reason | t | first tool call | calls | late | fallback? |
|---|---|---:|---:|---:|---:|---|
| wake_0001 | event:evt_0004 DANGER | 54.2 | 5.3 s | 3 | 0 | no |
| wake_0002 | event:evt_0006 VICTIM_FOUND | 66.0 | 9.6 s | 2 | 0 | no |
| wake_0003 | event:evt_0009 MAYDAY | 92.1 | 6.7 s | 5 | 0 | no. The gap fill sent router briefs to rit and hanbit_center. |
| wake_0004 | event:evt_0010 HELP_NEEDED | 102.7 | 11.1 s (12.07 s by `first_call_ms`) | 3 | 3 | **timeout** |
| wake_0005 | proposal_approved:prop_0002 | 108.1 | 7.7 s (get_unit_state) | 2 | 1 | **timeout** |
| wake_0006 | proposal_approved:prop_0003 | 108.2 | 4.7 s (get_unit_state) | 2 | 1 | **timeout** |
| wake_0007 | event:evt_0011 MAYDAY | 129.7 | 8.3 s | 7 | 0 | no |
| wake_0008 | rule:R2:park | 144.0 | 5.0 s (get_unit_state) | 2 | 1 | **timeout** |

## Notes / findings

1. **The run ends before the last line is triaged.** `running` turned false at t=167.2, but L13 (key-up 155.0, t_end 163.0, final 164.5) became `evt_0012` and resolved R2 only at about t=168.7.
   - A state captured the moment `running` goes false still shows R2 escalated with no event for L13. The run file does contain the resolution.
   - The UI will show "stopped" for about 1.5 s while the final "found OK" is still on its way.
   - The fix is either to set `running=false` only after in-flight triage finishes, or to have the poller wait about 3 s.
2. **The fallback FAIL comes from two-round wakes, not from truncation.**
   - In wakes 5, 6 and 8, round 1 returned only a read tool (`get_unit_state`). Round 2 (effort "low") then ran past the 12 s timeout.
   - Wake 4 (HELP_NEEDED) was a single slow round-1 response, at 12.07 s.
   - The two `proposal_approved:*` wakes add work that run 1 did not have. They are 2 of the 4 fallbacks, and in each the router or world had already delivered the approval briefs.
   - Possible fixes, any of which would fix this:
     - stop counting `proposal_approved` wakes, or skip them;
     - put the unit state into the snapshot so round 1 doesn't need `get_unit_state`;
     - forbid read-only first rounds.
3. **Bug: an auto-escalation fires after the ack.** At t=153.1 the late wake_0005 traced an auto `escalate_to_ic` with `{event_id: null, reason: "invariant 5: MAYDAY unacked"}`. The MAYDAY `card_0003` had been acked at t=107.8. `_ensure_mayday_escalated` runs on late wake completion without checking the card state. The card stayed acked, so this is trace noise, but it reads as wrong in the trace panel.
4. **Late duplicate RIT_DEPLOY from wake_0004.** Its text was "신속동료구조팀 동측 창문 투입 (동측 창문)" (the zone is the access point). It was deduped because a RIT_DEPLOY already existed, so there is no user-visible effect.
5. **A 4th ping to park after he reported OK.** wake_0008's late `ping_unit(park)` landed at t=167.2. That was after park's L13 transmission at key-up 155, but before L13 was triaged, so park got ping_0004 just as R2 resolved. A late `ping_unit` could be dropped when the unit has been heard since the wake started.
6. **Prompt nudge works.** park's MAYDAY P0 at t=98.7 reads "…출구 확보 유의." There is no premature "무선 침묵" before the IC approved it.
7. **CONFIRM_STRATEGY** (`prop_0001`, rule) was still pending at the end, because the driver deliberately approved only RIT_DEPLOY and RADIO_SILENCE.

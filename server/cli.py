"""Dev CLI.

  uv run python -m server.cli triage "<text>" [--lang ko] [--channel TAC]
  uv run python -m server.cli replay --audio clean|radio --asr realtime|file --lang ko [--speed 4] [--max-t 70]
"""

from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

import argparse  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402

from server.gate import should_triage  # noqa: E402
from server.models import Event, Latency, Transmission, after_speech_ms  # noqa: E402
from server.triage import triage  # noqa: E402
from server.verify import snap_event  # noqa: E402


async def pipeline(tx: Transmission, lang: str, ev_n: list[int], keyup_wall: float | None = None,
                   asr_ms: int = 0) -> Event | None:
    text = tx.text_final or ""
    if not should_triage(text):
        print(f"t={tx.t_keyup:6.1f} {tx.channel:3} {tx.line_id or '-':4} GATED  text={text!r}", flush=True)
        return None
    tri, tri_ms, _usage = await triage(text, tx.lang or lang, tx.channel)
    ok, tri, unit, zone = snap_event(tri, text, tx.lang or lang)
    ev_n[0] += 1
    total = int((time.perf_counter() - keyup_wall) * 1000) if keyup_wall else 0
    ev = Event(id=f"evt_{ev_n[0]:04d}", transmission_id=tx.id, t=tx.t_keyup, channel=tx.channel, text=text,
               triage=tri, speaker_unit_snapped=unit, zone_id_snapped=zone,
               latency=Latency(asr_ms=asr_ms, triage_ms=tri_ms, total_ms=total,
                               after_speech_ms=after_speech_ms(total, tx.t_keyup, tx.t_end)), evidence_verified=ok,
               source=tx.source)
    print(f"t={ev.t:6.1f} {ev.channel:3} {tx.line_id or '-':4} {tri.tag:12} unit={unit} zone={zone} "
          f"floor={tri.location.floor} asr_ms={asr_ms} triage_ms={tri_ms} after_speech_ms={ev.latency.after_speech_ms} evidence_verified={ok} | {text}",
          flush=True)
    return ev


async def cmd_triage(args: argparse.Namespace) -> None:
    tri, ms, usage = await triage(args.text, args.lang, args.channel)
    ok, tri, unit, zone = snap_event(tri, args.text, args.lang)
    print(json.dumps(tri.model_dump(mode="json"), ensure_ascii=False, indent=1))
    print(f"tag={tri.tag} floor={tri.location.floor} unit_snapped={unit} zone_snapped={zone} "
          f"evidence_verified={ok} triage_ms={ms} usage={usage} gate={should_triage(args.text)}")


async def cmd_replay(args: argparse.Namespace) -> None:
    from server.scenario import ScenarioPlayer

    ev_n = [0]
    tasks: set[asyncio.Task] = set()

    def on_final(tx: Transmission) -> None:
        task = asyncio.create_task(pipeline(tx, args.lang, ev_n, player.keyup_wall.get(tx.id),
                                            player.asr_ms.get(tx.id, 0)))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def on_cue(cue: dict) -> None:
        print(f"t={cue['t']:6.1f} {cue['channel']:3} {cue['line_id']:4} audio_cue {cue['audio_url']}", flush=True)

    def on_ptt(line: dict) -> None:
        print(f"t={line['t']:6.1f} PTT {line['id']:4} ptt line (main.py drives PTT socket) | {line.get('text_ko')}",
              flush=True)

    def on_agent(line: dict) -> None:
        print(f"t={line['t']:6.1f} --- {line['id']:4} agent line | {line.get('text_en')}", flush=True)

    player = ScenarioPlayer("hanbit", lang=args.lang, audio=args.audio, asr=args.asr, speed=args.speed,
                            max_t=args.max_t, on_final=on_final, on_audio_cue=on_cue, on_ptt_line=on_ptt,
                            on_agent_line=on_agent)
    await player.run()
    if tasks:
        await asyncio.wait(tasks, timeout=60)
    print(f"done: {ev_n[0]} events", flush=True)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="server.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage")
    t.add_argument("text")
    t.add_argument("--lang", default="ko")
    t.add_argument("--channel", default="TAC")
    r = sub.add_parser("replay")
    r.add_argument("--audio", default="clean", choices=["clean", "radio"])
    r.add_argument("--asr", default="realtime", choices=["realtime", "file"])
    r.add_argument("--lang", default="ko")
    r.add_argument("--speed", type=float, default=1.0)
    r.add_argument("--max-t", type=float, default=None, help="stop after this scenario second")
    args = p.parse_args()
    asyncio.run(cmd_triage(args) if args.cmd == "triage" else cmd_replay(args))


if __name__ == "__main__":
    main()

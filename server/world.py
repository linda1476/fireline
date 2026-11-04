"""World: the single source of truth for one run (docs/CONTRACT.md).

Holds a models.State, id counters, an append-only JSONL log, and applies Events / rule actions /
REST decisions. Every mutation broadcasts a WsMessage (type names per CONTRACT "WebSocket") through
the `broadcast` callback (sync or async) and is appended to the log.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

from server import rules
from server.config import ROOT, Settings, get_settings
from server.models import (
    DISTRESS_WHAT_KO, TAG_PRIORITY, Brief, Card, Counters, Event, HazardNote, Proposal, State,
    TraceEntry, Transmission, Unit, VictimReport, WsMessage, Zone,
)

Broadcast = Callable[[WsMessage], Awaitable[None] | None]
OPEN = ("open", "escalated")
MAYDAY_FIELDS = ["who", "what", "where", "needs", "air"]
KIND_KO = {"MAYDAY": "긴급탈출", "DANGER": "위험", "VICTIM_FOUND": "구조대상자", "HELP_NEEDED": "지원요청", "RULE": "규칙"}


def _nospace(s: str | None) -> str:
    return "".join((s or "").split()).lower()


class World:
    def __init__(
        self,
        scenario_id: str = "hanbit",
        lang: str = "ko",
        mode: str = "LIVE",
        thresholds: Settings | None = None,
        broadcast: Broadcast | None = None,
        *,
        log_path: str | Path | None = "auto",
        data_dir: Path | None = None,
    ):
        self.th = thresholds or get_settings()
        self._send = broadcast
        self.data_dir = data_dir or (ROOT / "data")
        self._ids: dict[str, int] = {}
        self.queue: list[Card] = []                 # overflow beyond max_open_cards (not in state.cards)
        self._card_last_t: dict[str, float] = {}    # last merge time per card (dedupe window)
        self.flags: dict[str, Any] = {"radio_silence": False}
        self.state = State(scenario_id=scenario_id, mode=mode, lang=lang)  # type: ignore[arg-type]
        self._load()
        if log_path == "auto":
            log_dir = self.data_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"world_{scenario_id}_{int(time.time())}.jsonl"
        self.log_path = Path(log_path) if log_path else None

    # ------------------------------------------------------------------ setup
    def _load(self) -> None:
        st = self.state
        scen: dict[str, Any] = {}
        sp = self.data_dir / f"scenario_{st.scenario_id}.yaml"
        if sp.exists():
            scen = yaml.safe_load(sp.read_text(encoding="utf-8")) or {}
        roster = json.loads((self.data_dir / "roster.json").read_text(encoding="utf-8"))["units"]
        wanted = scen.get("units") if scen.get("lang", "ko") == st.lang else None
        for u in roster:
            if (wanted and u["id"] in wanted) or (not wanted and u.get("lang", "ko") == st.lang):
                st.units[u["id"]] = Unit(**u)
        zones = json.loads((self.data_dir / "zones.json").read_text(encoding="utf-8"))
        for z in zones.get("zones", []):
            st.zones[z["id"]] = Zone(**z)
        st.building = {**zones.get("building", {}), **(scen.get("building") or {}),
                       "name_ko": scen.get("name_ko"), "name_en": scen.get("name_en")}
        st.strategy = scen.get("strategy_initial", "NONE") or "NONE"
        th = self.th
        st.thresholds = {
            "R1_ack_s": th.r1_ack_s, "R1_level2_s": th.r1_level2_s, "R2_silent_s": th.r2_silent_s,
            "R2_ping_gap_s": th.r2_ping_gap_s, "R2_pings": float(th.r2_pings), "R4_assign_s": th.r4_assign_s,
            "R5_exit_s": th.r5_exit_s, "max_open_cards": float(th.max_open_cards), "dedupe_window_s": th.dedupe_window_s,
        }

    # ------------------------------------------------------------------ plumbing
    def new_id(self, prefix: str) -> str:
        n = self._ids.get(prefix, 0) + 1
        self._ids[prefix] = n
        return f"{prefix}_{n:04d}"

    def clock(self) -> float:
        return self.state.t

    def set_t(self, t: float) -> None:
        self.state.t = float(t)

    def emit(self, type_: str, payload: Any) -> WsMessage:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        msg = WsMessage(type=type_, payload=payload)
        if self.log_path:
            try:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.time(), "t": self.state.t, "type": type_, "payload": payload},
                                       ensure_ascii=False) + "\n")
            except OSError:
                pass
        if self._send is not None:
            res = self._send(msg)
            if inspect.isawaitable(res):
                try:
                    asyncio.get_running_loop()
                    asyncio.ensure_future(res)
                except RuntimeError:
                    asyncio.run(res)  # no loop (CLI/tests)
        return msg

    def broadcast(self, type_: str, payload: Any) -> WsMessage:
        """agent.py-facing alias: world.broadcast("ask", {...})."""
        return self.emit(type_, payload)

    def escalate(self, card_id: str, level: int, reason: str | None = None) -> Card | None:
        """agent.py-facing alias (escalate_to_ic / invariant 5)."""
        return self.escalate_card(card_id, level, None)

    def _unit(self, uid: str | None) -> Unit | None:
        return self.state.units.get(uid) if uid else None

    def _card(self, cid: str) -> Card | None:
        return next((c for c in self.state.cards if c.id == cid), None)

    # ------------------------------------------------------------------ counters
    def recount(self, emit: bool = True) -> Counters:
        st, c = self.state, self.state.counters
        c.transmissions = len(st.transmissions)
        c.events = len(st.events)
        c.cards_open = sum(1 for x in st.cards if x.state in OPEN)
        c.cards_total = len(st.cards) + len(self.queue)
        c.cards_queued = len(self.queue)
        c.unacked = c.cards_open + len(self.queue)
        c.pushed = sum(1 for b in st.briefs if b.decision == "push")
        c.held = sum(max(0, u.total_count - u.heard_count) for u in st.units.values() if u.role == "CREW")
        if emit:
            self.emit("counters", c)
        return c

    # ------------------------------------------------------------------ transmissions
    def upsert_transmission(self, tx: Transmission) -> Transmission:
        txs = self.state.transmissions
        for i, old in enumerate(txs):
            if old.id == tx.id:
                txs[i] = tx
                break
        else:
            txs.append(tx)
            self.state.counters.transmissions = len(txs)
        self.emit("transmission", tx)
        return tx

    def _tx(self, tx_id: str) -> Transmission | None:
        return next((x for x in self.state.transmissions if x.id == tx_id), None)

    # ------------------------------------------------------------------ events
    def _speaker(self, ev: Event) -> str | None:
        if ev.speaker_unit_snapped in self.state.units:
            return ev.speaker_unit_snapped
        tx = self._tx(ev.transmission_id)
        if tx and tx.unit_id in self.state.units:
            return tx.unit_id
        return None

    def _match_unit_text(self, text: str | None) -> str | None:
        """Find a non-command unit mentioned in text (aliases, spaces stripped, longest first)."""
        s = _nospace(text)
        if not s:
            return None
        best: tuple[int, str] | None = None
        for u in self.state.units.values():
            if u.role in ("IC", "DISPATCH"):
                continue
            for a in [u.callsign, u.name or "", *u.aliases]:
                a2 = _nospace(a)
                if len(a2) >= 2 and a2 in s and (best is None or len(a2) > best[0]):
                    best = (len(a2), u.id)
        return best[1] if best else None

    def _subject_unit(self, ev: Event, speaker: str | None) -> str | None:
        """The unit a card is about: the speaker, unless Command/Dispatch is talking about someone else."""
        su = self._unit(speaker)
        if su is not None and su.role not in ("IC", "DISPATCH"):
            return speaker
        tr = ev.triage
        for txt in ((tr.distress.who if tr.distress else None), tr.addressee, tr.speaker_unit if not su else None):
            uid = self._match_unit_text(txt)
            if uid:
                return uid
        if tr.tag == "MAYDAY":
            uid = self._match_unit_text(ev.text)
            if uid:
                return uid
            open_md = [c for c in self.state.cards if c.kind == "MAYDAY" and c.state != "resolved" and c.unit_id]
            if open_md:
                return open_md[-1].unit_id
        return speaker

    def _zone_label(self, zid: str | None) -> str | None:
        z = self.state.zones.get(zid) if zid else None
        return (z.label_ko if self.state.lang == "ko" else z.label_en) if z else None

    def _zones_match(self, a: str | None, b: str | None) -> bool:
        if a is None or b is None or a == b:
            return True
        za, zb = self.state.zones.get(a), self.state.zones.get(b)
        return bool((za and za.parent == b) or (zb and zb.parent == a))

    def _fields(self, kind: str, ev: Event, unit_id: str | None) -> dict[str, str | None]:
        tr = ev.triage
        u = self._unit(unit_id)
        where = self._zone_label(ev.zone_id_snapped) or (tr.distress.where_raw if tr.distress else None) \
            or (tr.victims.where_raw if tr.victims else None) or tr.location.raw or tr.location.zone_hint
        if kind in ("MAYDAY", "HELP_NEEDED"):
            who = f"{u.callsign} {u.name}" if u and u.name else (u.callsign if u else None)
            who = who or (tr.distress.who if tr.distress else None) or tr.speaker_unit
            what = None
            if tr.distress and tr.distress.what not in ("UNKNOWN",):
                what = DISTRESS_WHAT_KO.get(tr.distress.what, tr.distress.what)
            needs = tr.distress.needs if tr.distress else None
            if kind == "HELP_NEEDED" and not needs:
                needs = tr.evidence_span or None
            return {"who": who, "what": what, "where": where, "needs": needs,
                    "air": tr.distress.air if tr.distress else None}
        if kind == "VICTIM_FOUND":
            v = tr.victims
            return {"count": str(v.count) if v and v.count is not None else None, "where": where,
                    "state": v.state if v and v.state != "UNKNOWN" else None}
        if kind == "DANGER":
            return {"where": where, "terms": ", ".join(tr.hazard_terms) or None}
        return {"where": where}

    @staticmethod
    def _missing(fields: dict[str, str | None]) -> list[str]:
        return [k for k, v in fields.items() if v in (None, "")]

    def _title(self, kind: str, fields: dict[str, str | None], unit_id: str | None, zone_id: str | None) -> tuple[str, str]:
        u = self._unit(unit_id)
        who_ko = (f"{u.callsign} {u.name}" if u and u.name else u.callsign) if u else (fields.get("who") or "")
        who_en = (u.label_en or u.callsign) if u else (fields.get("who") or "")
        where = zone_id or fields.get("where") or "?"
        if kind == "VICTIM_FOUND":
            n = fields.get("count") or "?"
            return f"구조대상자 {n}명 · {where}", f"VICTIM {n} · {where}"
        if kind == "DANGER":
            return f"위험 · {where} · {fields.get('terms') or ''}".rstrip(" ·"), f"DANGER · {where}"
        parts_ko = [KIND_KO.get(kind, kind), who_ko, where]
        parts_en = [kind.replace("_", " "), who_en, where]
        return " · ".join(p for p in parts_ko if p), " · ".join(p for p in parts_en if p)

    def _open_count(self) -> int:
        return sum(1 for c in self.state.cards if c.state in OPEN)

    def _place_card(self, card: Card) -> None:
        """≤ max_open_cards open|escalated; priority-0 cards (MAYDAY / R2) are never queued."""
        if card.priority > 0 and self._open_count() >= self.th.max_open_cards:
            self.queue.append(card)
            self.queue.sort(key=lambda c: (c.priority, c.created_t))
        else:
            self.state.cards.append(card)
            self.emit("card", card)

    def _promote(self) -> None:
        while self.queue and self._open_count() < self.th.max_open_cards:
            card = self.queue.pop(0)
            self.state.cards.append(card)
            self.emit("card", card)

    def _find_merge(self, kind: str, unit_id: str | None, zone_id: str | None, t: float) -> Card | None:
        pool = [c for c in [*self.state.cards, *self.queue] if c.state != "resolved"]
        if kind == "HELP_NEEDED" and unit_id:
            md = [c for c in pool if c.kind == "MAYDAY" and c.unit_id == unit_id]
            if md:
                return md[-1]
        for c in reversed(pool):
            if c.kind != kind or c.unit_id != unit_id:
                continue
            last = self._card_last_t.get(c.id, c.created_t)
            if t - last > self.th.dedupe_window_s:
                continue
            if kind == "MAYDAY" or self._zones_match(c.zone_id, zone_id):
                return c
        return None

    def _card_from_event(self, ev: Event, speaker: str | None) -> Card:
        kind = ev.triage.tag
        unit_id = self._subject_unit(ev, speaker)
        zone_id = ev.zone_id_snapped
        fields = self._fields(kind, ev, unit_id)
        existing = self._find_merge(kind, unit_id, zone_id, ev.t)
        if existing is not None:
            if ev.id not in existing.event_ids:
                existing.event_ids.append(ev.id)
            src = fields
            if existing.kind == "MAYDAY" and kind == "HELP_NEEDED":
                src = {"needs": fields.get("needs"), "where": fields.get("where"), "air": fields.get("air")}
            for k, v in src.items():
                if v and not existing.fields.get(k):
                    existing.fields[k] = v
            existing.missing_fields = self._missing(existing.fields)
            if existing.zone_id is None and zone_id:
                existing.zone_id = zone_id
            self._card_last_t[existing.id] = ev.t
            if existing in self.state.cards:
                self.emit("card", existing)
            return existing
        title, title_en = self._title(kind, fields, unit_id, zone_id)
        card = Card(
            id=self.new_id("card"), kind=kind, title=title, title_en=title_en, event_ids=[ev.id],
            priority=TAG_PRIORITY.get(kind, 9), unit_id=unit_id, zone_id=zone_id, fields=fields,
            missing_fields=self._missing(fields), evidence_span=ev.triage.evidence_span, channel=ev.channel,
            created_t=ev.t, latency_ms=ev.latency.total_ms,
        )
        self._card_last_t[card.id] = ev.t
        self._place_card(card)
        return card

    def _heard_from(self, unit_id: str, t: float, note_src: str) -> None:
        u = self._unit(unit_id)
        if not u:
            return
        u.last_heard_t = t
        u.unanswered_pings = 0
        for c in self.state.cards:
            if c.kind == "RULE" and c.rule_id == "R2" and c.unit_id == unit_id and c.state != "resolved":
                c.state = "resolved"
                c.resolved_t = t
                c.note = f"found OK ({note_src})"
                self.emit("card", c)
        self._promote()

    def apply_event(self, ev: Event) -> list[Card]:
        st = self.state
        st.events.append(ev)
        self.emit("event", ev)
        tr = ev.triage
        speaker = self._speaker(ev)
        changed: set[str] = set()
        tx = self._tx(ev.transmission_id)

        # heard N of M: every transmission counts for every unit except its speaker
        for u in st.units.values():
            if u.id != speaker:
                u.total_count += 1
        if speaker:
            self._heard_from(speaker, ev.t, (tx.line_id if tx and tx.line_id else ev.id))
            changed.add(speaker)
            u = st.units[speaker]
            sc = tr.status_change
            if sc == "ENTERING":
                u.status, u.interior = "IN", True
            elif sc == "EXITING":
                u.status, u.interior = "OUT", False
            elif sc in ("TRAPPED", "LOW_AIR", "OK"):
                u.status = sc
            if ev.zone_id_snapped and u.role not in ("IC", "DISPATCH"):
                u.zone_id = ev.zone_id_snapped

        if tr.strategy_declared != "NONE":
            st.strategy = tr.strategy_declared
            st.strategy_event_id = ev.id
            self.emit("strategy", {"strategy": st.strategy, "event_id": ev.id})

        z = st.zones.get(ev.zone_id_snapped) if ev.zone_id_snapped else None
        if z is not None and tr.tag == "DANGER":
            z.hazards.append(HazardNote(event_id=ev.id, text=", ".join(tr.hazard_terms) or tr.evidence_span or ev.text, t=ev.t))
            self.emit("zone", z)
        if z is not None and tr.tag == "VICTIM_FOUND":
            v = tr.victims
            z.victim_reports.append(VictimReport(event_id=ev.id, count=v.count if v else None,
                                                 state=v.state if v else "UNKNOWN", text=tr.evidence_span or ev.text, t=ev.t))
            self.emit("zone", z)

        cards: list[Card] = []
        if tr.tag != "ROUTINE":
            cards.append(self._card_from_event(ev, speaker))

        for uid in changed:
            self.emit("unit", st.units[uid])
        if tr.tag == "DANGER":
            self.apply_actions(rules.r3_on_event(ev, st))
        self.recount()
        return cards

    # ------------------------------------------------------------------ cards (REST)
    def ack_card(self, card_id: str) -> Card | None:
        c = self._card(card_id)
        if c is None:
            return None
        c.state = "acked"
        c.acked_t = self.state.t
        self.emit("card", c)
        self._promote()
        self.recount()
        return c

    def resolve_card(self, card_id: str, note: str | None = None) -> Card | None:
        c = self._card(card_id)
        if c is None:
            return None
        c.state = "resolved"
        c.resolved_t = self.state.t
        if note:
            c.note = note
        self.emit("card", c)
        self._promote()
        self.recount()
        return c

    def escalate_card(self, card_id: str, level: int, rule_id: str | None = None) -> Card | None:
        c = self._card(card_id)
        if c is None or c.state in ("acked", "resolved"):
            return c
        if level <= c.escalation_level and c.state == "escalated":
            return c
        c.escalation_level = max(c.escalation_level, level)
        c.state = "escalated"
        self.emit("card", c)
        self.emit("escalation", {"card_id": c.id, "level": c.escalation_level, "rule_id": rule_id})
        return c

    # ------------------------------------------------------------------ proposals
    def add_proposal(self, kind: str, units: list[str], text: str, rationale: str, *,
                     evidence_event_id: str | None = None, card_id: str | None = None, source: str = "agent") -> Proposal:
        p = Proposal(id=self.new_id("prop"), card_id=card_id, kind=kind, units=list(units), text=text,  # type: ignore[arg-type]
                     rationale=rationale, evidence_event_id=evidence_event_id, created_t=self.state.t, source=source)  # type: ignore[arg-type]
        self.state.proposals.append(p)
        self.emit("proposal", p)
        return p

    def _proposal(self, pid: str) -> Proposal | None:
        return next((p for p in self.state.proposals if p.id == pid), None)

    def edit_proposal(self, pid: str, text: str) -> Proposal | None:
        p = self._proposal(pid)
        if p is None:
            return None
        p.text = text
        p.state = "edited"
        self.emit("proposal", p)
        return p

    def decide_proposal(self, pid: str, approve: bool) -> Proposal | None:
        p = self._proposal(pid)
        if p is None or p.state in ("approved", "rejected"):
            return p
        st = self.state
        p.state = "approved" if approve else "rejected"
        p.decided_t = st.t
        self.emit("proposal", p)
        if not approve:
            return p
        card = self._card(p.card_id) if p.card_id else None
        target_zone = card.zone_id if card else None
        if target_zone is None and p.evidence_event_id:
            ev = next((e for e in st.events if e.id == p.evidence_event_id), None)
            target_zone = ev.zone_id_snapped if ev else None
        if p.kind == "RADIO_SILENCE":
            self.flags["radio_silence"] = True
        elif p.kind == "RIT_DEPLOY":
            for u in st.units.values():
                if u.role == "RIT" or (u.id in p.units and u.role == "RIT"):
                    if target_zone:
                        u.zone_id = target_zone
                    u.assignment = f"RIT deploy {target_zone or ''}".strip()
                    self.emit("unit", u)
        elif p.kind == "WITHDRAW":
            for u in st.units.values():
                if u.interior:
                    u.assignment = "EXITING (withdraw)"
                    self.emit("unit", u)
        elif p.kind == "CONFIRM_STRATEGY":
            txt = p.text.upper()
            if "DEFENSIVE" in txt or "방어" in p.text:
                st.strategy = "DEFENSIVE"
            elif "OFFENSIVE" in txt or "공격" in p.text:
                st.strategy = "OFFENSIVE"
            st.strategy_event_id = p.evidence_event_id
            self.emit("strategy", {"strategy": st.strategy, "event_id": p.evidence_event_id})
        elif p.kind == "ASSIGN":
            for uid in p.units:
                u = self._unit(uid)
                if u:
                    u.assignment = target_zone or p.text
                    self.emit("unit", u)
        for uid in p.units:
            if uid in st.units:
                self.add_brief(uid, p.text, priority="P0", reason=f"IC approved {p.kind}",
                               evidence_event_id=p.evidence_event_id, source=p.source)
        self.recount()
        return p

    # ------------------------------------------------------------------ briefs / trace / pings
    def add_brief(self, unit_id: str, text: str, *, priority: str = "P1", reason: str = "", decision: str = "push",
                  evidence_event_id: str | None = None, source: str = "agent", lang: str | None = None) -> Brief:
        b = Brief(id=self.new_id("brief"), unit_id=unit_id, decision=decision, text=text, priority=priority,  # type: ignore[arg-type]
                  reason=reason, evidence_event_id=evidence_event_id, created_t=self.state.t, source=source,  # type: ignore[arg-type]
                  lang=lang or self.state.lang)  # type: ignore[arg-type]
        self.state.briefs.append(b)
        u = self._unit(unit_id)
        self.emit("brief", b)
        if decision == "push" and u is not None:
            u.heard_count += 1
            self.emit("unit", u)
        self.recount()
        return b

    def add_trace(self, wake_id: str, wake_reason: str, kind: str, payload: dict[str, Any] | None = None) -> TraceEntry:
        e = TraceEntry(id=self.new_id("tr"), t=self.state.t, wake_id=wake_id, wake_reason=wake_reason,
                       kind=kind, payload=payload or {})  # type: ignore[arg-type]
        self.state.trace.append(e)
        self.emit("trace", e)
        return e

    def ping_unit(self, unit_id: str, source: str = "rule") -> dict[str, Any] | None:
        u = self._unit(unit_id)
        if u is None:
            return None
        u.unanswered_pings += 1
        u.total_count += 1
        ping = {"unit_id": unit_id, "n": u.unanswered_pings, "t": self.state.t, "ping_id": self.new_id("ping")}
        self.emit("ping", ping)
        self.emit("unit", u)
        if source == "rule":
            self.add_trace(ping["ping_id"], f"rule:R2:{unit_id}", "delivery",
                           {"ping": ping, "unit_id": unit_id, "decision": "push"})
        return ping

    def crew_ack(self, unit_id: str) -> Unit | None:
        u = self._unit(unit_id)
        if u is None:
            return None
        self._heard_from(unit_id, self.state.t, "crew ack")
        self.emit("unit", u)
        self.recount()
        return u

    # ------------------------------------------------------------------ rules
    def apply_actions(self, actions: list[rules.Action]) -> None:
        for a in actions:
            if isinstance(a, rules.Escalate):
                self.escalate_card(a.card_id, a.level, a.rule_id)
            elif isinstance(a, rules.Ping):
                self.ping_unit(a.unit_id)
            elif isinstance(a, rules.RuleCard):
                u = self._unit(a.unit_id)
                if u:
                    u.total_count += 1
                fields = {"who": (f"{u.callsign} {u.name}" if u and u.name else (u.callsign if u else a.unit_id)),
                          "what": "3회 무응답", "where": self._zone_label(a.zone_id),
                          "last_heard": rules._fmt_t(a.last_heard_t)}
                card = Card(id=self.new_id("card"), kind="RULE", title=a.title, title_en=a.title_en, rule_id=a.rule_id,
                            priority=a.priority, unit_id=a.unit_id, zone_id=a.zone_id, fields=fields,
                            missing_fields=self._missing(fields), created_t=self.state.t)
                self._place_card(card)
            elif isinstance(a, rules.ProposeOrder):
                self.add_proposal(a.kind, a.units, a.text, a.rationale, evidence_event_id=a.evidence_event_id,
                                  card_id=a.card_id, source="rule")

    def tick(self, t: float) -> list[rules.Action]:
        self.set_t(t)
        actions = rules.evaluate(self.state, t, self.th)
        if actions:
            self.apply_actions(actions)
            self.recount()
        return actions

    # ------------------------------------------------------------------ agent view
    def snapshot_for_agent(self) -> dict[str, Any]:
        st = self.state
        briefs_by_unit: dict[str, list[dict[str, Any]]] = {}
        for b in st.briefs:
            briefs_by_unit.setdefault(b.unit_id, []).append(
                {"id": b.id, "text": b.text, "priority": b.priority, "decision": b.decision, "t": b.created_t})
        return {
            "t": st.t,
            "strategy": st.strategy,
            "radio_silence": self.flags.get("radio_silence", False),
            "units": [
                {"id": u.id, "callsign": u.callsign, "name": u.name, "role": u.role, "status": u.status,
                 "interior": u.interior, "zone_id": u.zone_id, "assignment": u.assignment,
                 "last_heard_t": u.last_heard_t, "unanswered_pings": u.unanswered_pings,
                 "heard": u.heard_count, "total": u.total_count}
                for u in st.units.values()
            ],
            "zones": [
                {"id": z.id, "label_ko": z.label_ko, "floor": z.floor, "parent": z.parent,
                 "hazards": [h.text for h in z.hazards], "victims": [v.count for v in z.victim_reports],
                 "search_state": z.search_state}
                for z in st.zones.values()
            ],
            "open_cards": [
                {"id": c.id, "kind": c.kind, "title": c.title, "unit_id": c.unit_id, "zone_id": c.zone_id,
                 "state": c.state, "escalation_level": c.escalation_level, "fields": c.fields,
                 "missing_fields": c.missing_fields, "event_ids": c.event_ids, "created_t": c.created_t}
                for c in st.cards if c.state in OPEN
            ],
            "recent_briefs": {k: v[-3:] for k, v in briefs_by_unit.items()},
        }

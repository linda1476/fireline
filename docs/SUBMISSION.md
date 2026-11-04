# Submission checklist — Meta Global AI Developer Hackathon 2026

**Deadline: Wed 4 Nov 2026, 9:00 PM ET = Thu 5 Nov 11:00 KST.** Late = not judged.

Track: **Indie Developer** (solo). Theme: **Build for Your World**.

## Must do (in order)
1. [ ] Claim the $150 Meta Model API credits — form is in the Cerebral Valley participant
       guide (https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details). Also closes
       4 Nov 9 PM ET. Set a spend limit at https://dev.meta.ai/billing.
2. [ ] `MODEL_API_KEY` in `D:\meta\.env`; `uv run python scripts/smoke_meta.py` → ALL OK.
3. [ ] Record the 3-minute demo video (docs/VIDEO_SCRIPT.md). Upload to YouTube
       (unlisted is fine) — copy the link.
4. [ ] Make the repo public: `gh repo edit linda1476/fireline --visibility public --accept-visibility-change-consequences`
5. [ ] README has: problem + sources, what it does, the three Meta models and how each is
       used (judges score "use of Meta AI tooling" 25%), architecture, how to run, demo
       output, honest limitations (hardware simulated), video link.
6. [ ] Submit on the CV platform: project name, tagline, track, theme, video link, repo
       link, description. Only the designated submitter submits; list all contributors.
7. [ ] Optional: post the demo on X and paste the post link in the submission ("Most
       Viral" bonus); the public gallery community vote opens 9 Nov.

## Suggested submission text
**Name:** Fireline
**Tagline:** Every radio call triaged, every crew on one map, every firefighter told only what they need to hear — on the Meta Model API.
**Description (≤ 150 words):** Fireline is an indoor/outdoor coordination harness for
structure fires. Muse Voice Transcribe streams every radio transmission to text; Muse
Spark 1.3 extracts a structured event (priority tag, floor, zone, victims, hazards,
needs) that drives a commander's priority queue; a pure-Python world model fuses those
events with one-touch inputs from a clip-on display and SAM 3.1 helmet-cam detections
into one shared floor-plan state; and a Spark-based briefing agent decides, per
responder, whether to interrupt them through a bone-conduction earpiece and what to say
(“Ladder 2: stairwell B blocked above you, use A”). Built because investigations in
Mungyeong (2024), Pyeongtaek (2022) and Bridgeport (2010) all found the same failure:
transmissions that were made but not heard, and crews whose location nobody held. The
clip-on hardware is simulated on a phone; everything else runs.

## Judging rubric (self-check)
- Impact 30% — sourced problem, clear beneficiary (crews + command), realistic next step.
- Meta tooling 25% — three surfaces (ASR realtime + file, Spark structured output + agent, SAM) used for what they are good at, not a chatbot wrapper.
- Demo 25% — the mayday beat must land: queue flash → map → spoken briefing in < 5 s.
- Technical depth 20% — world model rules, zone normalisation, agent decision policy, tests.
Pass/fail gates: theme fit (yes), genuine Meta model use (yes — must be live in the video, badges visible).

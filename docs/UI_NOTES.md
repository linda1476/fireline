# UI findings from the first browser pass (sample data, 1920×1080 dark)

Checked `/command?sample=1`, `/demo?sample=1`, `/crew/kim?sample=1` in the built-in browser.

## Works
- `/command`: lanes with partial/final + unit + time + ▶, card queue with SOP 109 fields (missing `needs` highlighted),
  evidence quote, latency badge, ack timer with "demo timescale", proposal with Approve/Reject/Edit, map (2F zones, hazards
  amber, victim pin, units), accountability strip with red last-heard age. No runtime errors.
- `/crew/kim`: header (unit, zone, status, heard N of M), 4 hold buttons, TALK, footer label.

## Must fix
1. `/demo` page scrolls: `document.documentElement.scrollHeight` = 1594 at 1080 high. The demo must be `h-screen`
   `overflow-hidden` with internal scroll regions (lanes, card queue, trace) so OBS captures everything; the two phones
   must fit at 0.8 scale beside the command view.
2. `/demo` left pane (60 % = 1152 px) is too cramped for the three-column command layout: use a demo-specific layout —
   lanes (left ~300 px) · cards (centre, flexible) · map (right ~320 px, Map only; Trace as a toggle) · accountability
   strip at the bottom at smaller row height. Top bar must stay visible (clock, mode badge, counters).
3. `/crew/:unit` brief text is rendered dim/grey (looks like a disabled state) — the current brief must be the brightest,
   largest text on the screen (line 2 ≥ 28 px, white), with the tag chip in its colour and the "why" line muted.
4. Sample mode (`?sample=1`) still opens the WebSocket and spams 502s in the console; skip connecting when sample data
   is used.
5. In `/demo`, the phones should show a small unit label above each frame ("FF Kim · 2F east", "FF Park · 1F west").

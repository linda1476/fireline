/* Fireline command dashboard.
 *
 * Codes against docs/CONTRACT.md exactly:
 *   GET  /api/state, /api/health
 *   POST /api/ack {report_id}, /api/assignment {assignment_id, accepted},
 *        /api/report {responder_id, text, source:"text"}, /api/demo/run {mode},
 *        /api/demo/reset, /api/mic/start {responder_id}, /api/mic/stop
 *   WS   /ws  -> "state" | "delta" | "transcript" | "briefing" | "assignment" | "event" | "error"
 *
 * Rendering model: every "state" message re-renders everything (state is small).
 * "delta" / "briefing" / "assignment" / "transcript" drive animations, toasts, the
 * briefing + assignment logs (which are NOT part of WorldState) and the ticker.
 *
 * Dev harness: open with ?mock=1 and no server is contacted; an inline scenario
 * drives the UI through the same handleMessage() path the WebSocket uses.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  // ?mock=1 (or window.FIRELINE_MOCK = 1 for inlined previews) => offline dev harness.
  var MOCK = /(?:^|[?&])mock=1(?:&|$)/.test(location.search) || window.FIRELINE_MOCK === 1;
  var FLOORS = [0, 1, 2, 3, 4, 5];
  var STATUS_COLOR = { OK: '#3ddc84', InDanger: '#ff3b3b', NeedsHelp: '#4f9cff', Evacuating: '#ffb020', Unknown: '#6c7a89' };
  var TAG_LABEL = { Danger: 'DANGER', VictimFound: 'VICTIM', HelpNeeded: 'HELP', Status: 'STATUS' };
  var EVENT_LABEL = { report: 'RADIO', triage: 'TRIAGE', touch: 'TOUCH', photo: 'CAM', briefing: 'BRIEF', assignment: 'ASSIGN', system: 'SYS' };

  // ---------------------------------------------------------------------------
  // Client state
  // ---------------------------------------------------------------------------
  var S = {
    state: null,            // last WorldState snapshot
    lastVersion: -1,
    floor: 1,               // selected floor tab (0 = site)
    autoFloor: true,
    pendingFloor: null,     // floor to switch to on the next "state" render
    pendingResponder: null, // responder whose floor we switch to if triage had none
    pulse: { responders: {}, victims: {}, hazards: {} },
    briefings: [],          // newest first
    assignments: [],        // newest first
    seenMayday: {},
    health: null,
    micOn: false,
    ws: null,
    wsBackoff: 1000,
    rosterKey: ''
  };

  var $ = function (id) { return document.getElementById(id); };

  // ---------------------------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------------------------
  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    setAttrs(n, attrs);
    appendAll(n, children);
    return n;
  }
  function svg(tag, attrs, children) {
    var n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    setAttrs(n, attrs);
    appendAll(n, children);
    return n;
  }
  function setAttrs(n, attrs) {
    if (!attrs) return;
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined) return;
      if (k === 'text') n.textContent = v;
      else if (k === 'cls') n.setAttribute('class', v);
      else if (k === 'on') Object.keys(v).forEach(function (ev) { n.addEventListener(ev, v[ev]); });
      else n.setAttribute(k, v);
    });
  }
  function appendAll(n, children) {
    if (!children) return;
    (Array.isArray(children) ? children : [children]).forEach(function (c) {
      if (c === null || c === undefined) return;
      n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function values(obj) { return obj ? Object.keys(obj).map(function (k) { return obj[k]; }) : []; }

  // ---------------------------------------------------------------------------
  // Formatting
  // ---------------------------------------------------------------------------
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function fmtClock(d) { return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()); }
  function fmtTime(iso) {
    var t = Date.parse(iso || '');
    if (isNaN(t)) return '--:--:--';
    return fmtClock(new Date(t));
  }
  function fmtAge(iso) {
    var t = Date.parse(iso || '');
    if (isNaN(t)) return '';
    var s = Math.max(0, Math.floor((Date.now() - t) / 1000));
    var m = Math.floor(s / 60), h = Math.floor(m / 60);
    if (h > 0) return h + ':' + pad2(m % 60) + ':' + pad2(s % 60);
    return m + ':' + pad2(s % 60);
  }
  function floorLabel(f) {
    if (f === null || f === undefined) return '?';
    return f === 0 ? 'SITE' : f + 'F';
  }
  function callsign(rid) { return rid || '—'; }
  function responderFloor(r) { return r && r.cell ? r.cell.floor : null; }

  // ---------------------------------------------------------------------------
  // HTTP
  // ---------------------------------------------------------------------------
  function api(path, body, method) {
    var opts = { method: method || (body === undefined ? 'GET' : 'POST'), headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (!res.ok) throw new Error(path + ' -> HTTP ' + res.status);
      return res.text().then(function (t) { try { return t ? JSON.parse(t) : {}; } catch (e) { return {}; } });
    });
  }
  function post(path, body) {
    if (MOCK) return Mock.handlePost(path, body || {});
    return api(path, body || {}).catch(function (err) { toast('error', 'REQUEST FAILED', String(err.message || err)); throw err; });
  }

  // ---------------------------------------------------------------------------
  // WebSocket (auto-reconnect with capped backoff)
  // ---------------------------------------------------------------------------
  function wsUrl() { return (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/ws'; }

  function connect() {
    if (MOCK) return;
    var ws;
    try { ws = new WebSocket(wsUrl()); } catch (e) { scheduleReconnect(); return; }
    S.ws = ws;
    ws.onopen = function () {
      S.wsBackoff = 1000;
      setConn(true);
      // The server sends a fresh "state" on connect; refetch too in case it does not.
      api('/api/state').then(function (st) { if (st && st.building) handleMessage({ type: 'state', payload: st }); }).catch(function () {});
      fetchHealth();
    };
    ws.onmessage = function (ev) {
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      try { handleMessage(msg); } catch (e) { console.error('handleMessage', e, msg); }
    };
    ws.onclose = function () { setConn(false); scheduleReconnect(); };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }
  function scheduleReconnect() {
    setTimeout(connect, S.wsBackoff);
    S.wsBackoff = Math.min(S.wsBackoff * 2, 10000);
  }
  function setConn(on) {
    var c = $('conn');
    c.className = 'badge conn ' + (on ? 'on' : 'off');
    c.textContent = on ? 'WS ●' : 'WS ○';
    c.title = on ? 'WebSocket connected' : 'WebSocket disconnected — reconnecting';
  }

  // ---------------------------------------------------------------------------
  // Message dispatch
  // ---------------------------------------------------------------------------
  function handleMessage(msg) {
    if (!msg || typeof msg !== 'object') return;
    var p = msg.payload || {};
    switch (msg.type) {
      case 'state': onState(p); break;
      case 'delta': onDelta(p); break;
      case 'transcript': onTranscript(p); break;
      case 'briefing': onBriefing(p); break;
      case 'assignment': onAssignment(p); break;
      case 'event': onEvent(p); break;
      case 'error': toast('error', 'SERVER ERROR', p.message || p.detail || JSON.stringify(p)); break;
      default: break;
    }
  }

  function onState(st) {
    if (!st || !st.building) return;
    var v = typeof st.version === 'number' ? st.version : 0;
    if (S.state && v < S.lastVersion) resetClientLogs();     // scenario reset on the server
    S.lastVersion = v;
    S.state = st;
    applyPendingFloor();
    detectMayday();
    renderAll();
  }

  function resetClientLogs() {
    S.briefings = [];
    S.assignments = [];
    S.seenMayday = {};
    S.pulse = { responders: {}, victims: {}, hazards: {} };
    setTicker('', 'scenario reset', true, true);
  }

  function onDelta(d) {
    if (!d) return;
    var tri = d.triage;
    S.pendingFloor = null;
    S.pendingResponder = null;
    if (tri && typeof tri.floor === 'number') S.pendingFloor = tri.floor;
    else if (d.touch && d.touch.cell && typeof d.touch.cell.floor === 'number') S.pendingFloor = d.touch.cell.floor;
    else if (d.changed_responders && d.changed_responders.length) S.pendingResponder = d.changed_responders[0];
    (d.changed_responders || []).forEach(function (id) { S.pulse.responders[id] = true; });
    (d.changed_victims || []).forEach(function (id) { S.pulse.victims[id] = true; });
    (d.changed_hazards || []).forEach(function (id) { S.pulse.hazards[id] = true; });
    if (tri && tri.mayday) {
      toast('critical', 'MAYDAY', callsign(tri.responder_id) + ' — ' + (tri.zone || '?') + ' ' + floorLabel(tri.floor) + ': ' + (tri.summary || ''));
    } else if (tri && tri.tag === 'VictimFound' && tri.victim_certainty === 'confirmed') {
      toast('high', 'VICTIM CONFIRMED', (tri.zone || '?') + ' ' + floorLabel(tri.floor) + ' — ' + (tri.summary || ''));
    }
  }

  function applyPendingFloor() {
    if (!S.autoFloor) { S.pendingFloor = null; S.pendingResponder = null; return; }
    var f = S.pendingFloor;
    if (f === null && S.pendingResponder && S.state.responders) {
      var r = S.state.responders[S.pendingResponder];
      f = responderFloor(r);
    }
    if (typeof f === 'number' && FLOORS.indexOf(f) >= 0) S.floor = f;
    S.pendingFloor = null;
    S.pendingResponder = null;
  }

  function detectMayday() {
    var fresh = false;
    (S.state.queue || []).forEach(function (q) {
      var id = q.report && q.report.id;
      if (q.triage && q.triage.mayday && id && !S.seenMayday[id]) { S.seenMayday[id] = true; fresh = true; }
    });
    if (fresh) flashQueueColumn();
  }

  function flashQueueColumn() {
    var col = $('queue-col');
    col.classList.remove('flash');
    void col.offsetWidth; // restart the animation
    col.classList.add('flash');
    col.addEventListener('animationend', function h() { col.classList.remove('flash'); col.removeEventListener('animationend', h); });
  }

  function onTranscript(t) {
    var who = t.responder_id || (t.speaker ? 'spk ' + t.speaker : '');
    setTicker(who, t.text || '', !!t.final);
  }
  function setTicker(who, text, final, system) {
    var tk = $('ticker');
    tk.querySelector('.speaker').textContent = who ? who + ' ›' : '';
    var tx = tk.querySelector('.text');
    tx.textContent = text;
    tx.className = 'text' + (final ? '' : ' partial') + (system ? ' dim' : '');
  }

  function onBriefing(b) {
    if (!b || !b.id) return;
    if (S.briefings.some(function (x) { return x.id === b.id; })) return;
    S.briefings.unshift(b);
    if (S.briefings.length > 200) S.briefings.length = 200;
    renderBriefings();
    var urg = b.urgency || 'normal';
    if (urg === 'critical' || urg === 'high') toast(urg, 'BRIEF → ' + callsign(b.responder_id), b.text || '');
  }

  function onAssignment(a) {
    if (!a || !a.id) return;
    var idx = -1;
    S.assignments.forEach(function (x, i) { if (x.id === a.id) idx = i; });
    if (idx >= 0) S.assignments[idx] = a; else S.assignments.unshift(a);
    renderAssignments();
    if (idx < 0 && (a.accepted === null || a.accepted === undefined)) toast('ok', 'ASSIGNMENT PROPOSED', callsign(a.responder_id) + ' → ' + targetLabel(a));
  }

  function onEvent(e) {
    if (!e || !e.id || !S.state) return;
    var evs = S.state.events || (S.state.events = []);
    if (evs.some(function (x) { return x.id === e.id; })) return;
    evs.push(e);
    renderTimeline();
  }

  // ---------------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------------
  function renderAll() {
    if (!S.state) return;
    renderTopbar();
    renderRosterSelects();
    renderQueue();
    renderFloorTabs();
    renderMap();
    renderLegend();
    renderResponders();
    renderBriefings();
    renderAssignments();
    renderTimeline();
    S.pulse = { responders: {}, victims: {}, hazards: {} };
  }

  function renderTopbar() {
    var inc = $('incident');
    inc.textContent = S.state.incident_name || 'Incident';
    inc.title = S.state.incident_name || '';
  }

  function renderHealth() {
    var h = S.health;
    ['spark', 'asr', 'sam'].forEach(function (k) {
      var b = $('badge-' + k);
      var label = k.toUpperCase();
      if (!h) { b.className = 'badge unknown'; b.textContent = label + ' ?'; return; }
      var live = !h.mock;
      var m = h.models && h.models[k];
      if (m && typeof m === 'object') {
        if (typeof m.live === 'boolean') live = m.live;
        else if (typeof m.mock === 'boolean') live = !m.mock;
      }
      var name = m && typeof m === 'object' ? (m.model || m.name || '') : (typeof m === 'string' ? m : '');
      b.className = 'badge ' + (live ? 'live' : 'mock');
      b.textContent = label + ' ' + (live ? 'live' : 'mock');
      b.title = (name ? name + ' — ' : '') + (h.version ? 'server ' + h.version : '');
    });
  }
  function fetchHealth() {
    if (MOCK) { S.health = { mock: true, models: { spark: 'mock', asr: 'mock', sam: 'mock' }, version: 'mock' }; renderHealth(); return; }
    api('/api/health').then(function (h) { S.health = h; renderHealth(); }).catch(function () { S.health = null; renderHealth(); });
  }

  function renderRosterSelects() {
    var ids = Object.keys(S.state.responders || {});
    var key = ids.join('|');
    if (key === S.rosterKey) return;
    S.rosterKey = key;
    ['mic-speaker', 'inject-speaker'].forEach(function (sid) {
      var sel = $(sid), prev = sel.value;
      clear(sel);
      ids.forEach(function (id) { sel.appendChild(el('option', { value: id, text: id })); });
      if (ids.indexOf(prev) >= 0) sel.value = prev;
    });
  }

  // --- priority queue ------------------------------------------------------
  function renderQueue() {
    var box = $('queue');
    clear(box);
    var items = S.state.queue || [];
    $('queue-count').textContent = items.length ? '(' + items.filter(function (q) { return !q.acknowledged; }).length + ' open)' : '';
    if (!items.length) { box.appendChild(el('div', { cls: 'empty', text: 'No radio traffic yet. Run a demo or inject a line.' })); return; }
    items.forEach(function (q) { box.appendChild(queueCard(q)); });
  }

  function queueCard(q) {
    var tri = q.triage || {}, rep = q.report || {};
    var tag = tri.tag || 'Status';
    var r = S.state.responders[tri.responder_id || rep.responder_id];
    var cls = 'card tag-' + tag + (tri.mayday && !q.acknowledged ? ' mayday' : '') + (q.acknowledged ? ' acked' : '');
    var head = el('div', { cls: 'card-head' }, [
      el('span', { cls: 'chip ' + tag, text: TAG_LABEL[tag] || tag }),
      el('span', { cls: 'prio p' + tri.priority, text: 'P' + (tri.priority || '?') }),
      tri.mayday ? el('span', { cls: 'mayday-flag', text: 'MAYDAY' }) : null,
      el('span', { cls: 'age mono', 'data-ts': rep.timestamp || tri.timestamp || '', text: fmtAge(rep.timestamp || tri.timestamp) })
    ]);
    var meta = el('div', { cls: 'meta mono' }, [
      el('b', { text: callsign(tri.responder_id || rep.responder_id) }),
      r && r.name ? ' ' + r.name.split(' ').slice(-1)[0] : '',
      ' · ' + (tri.zone || '—') + ' · ' + floorLabel(tri.floor)
    ]);
    var action = q.acknowledged
      ? el('span', { cls: 'acked-lbl', text: 'ACKED' })
      : el('button', { cls: 'btn ack ok', text: 'ACK', on: { click: function () { ack(rep.id || tri.report_id, this); } } });
    var card = el('div', { cls: cls, title: rep.transcript || '' }, [
      head,
      el('div', { cls: 'summary', text: tri.summary || rep.transcript || '' }),
      meta,
      action
    ]);
    return card;
  }

  function ack(reportId, btn) {
    if (!reportId) return;
    if (btn) btn.disabled = true;
    post('/api/ack', { report_id: reportId }).catch(function () { if (btn) btn.disabled = false; });
  }

  function tickAges() {
    var nodes = document.querySelectorAll('#queue .age');
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = fmtAge(nodes[i].getAttribute('data-ts'));
  }

  // --- floor tabs ----------------------------------------------------------
  function floorStats(f) {
    var st = { resp: 0, victims: 0, danger: false };
    values(S.state.responders).forEach(function (r) {
      if (responderFloor(r) === f) { st.resp++; if (r.status === 'InDanger') st.danger = true; }
    });
    values(S.state.victims).forEach(function (v) { if (v.cell && v.cell.floor === f && v.status !== 'extracted') st.victims += (v.count || 1); });
    return st;
  }

  function renderFloorTabs() {
    var box = $('floor-tabs');
    clear(box);
    FLOORS.forEach(function (f) {
      var st = floorStats(f);
      var tab = el('button', { cls: 'ftab' + (f === S.floor ? ' active' : ''), type: 'button', title: 'Key ' + f, on: { click: function () { selectFloor(f, true); } } }, [
        f === 0 ? 'SITE' : String(f),
        st.danger ? el('span', { cls: 'dot danger' }) : null,
        st.victims ? el('span', { cls: 'dot victim' }) : null,
        st.resp ? el('span', { cls: 'n', text: st.resp + '●' }) : null
      ]);
      box.appendChild(tab);
    });
    var auto = $('btn-auto');
    auto.className = 'btn tiny' + (S.autoFloor ? ' on' : '');
    auto.textContent = S.autoFloor ? 'AUTO' : 'AUTO OFF';
  }

  function selectFloor(f, manual) {
    if (FLOORS.indexOf(f) < 0) return;
    S.floor = f;
    if (!S.state) return;
    renderFloorTabs();
    renderMap();
  }

  // --- map -----------------------------------------------------------------
  function renderMap() {
    var map = $('map');
    clear(map);
    var b = S.state.building;
    var f = S.floor, site = f === 0;
    var W = site ? (b.site_width || 60) : b.width;
    var H = site ? (b.site_height || 40) : b.height;
    var C = site ? 10 : 25; // SVG units per cell; both views end up ~600 units wide
    map.setAttribute('viewBox', '0 0 ' + (W * C) + ' ' + (H * C));
    map.appendChild(svg('rect', { x: 0, y: 0, width: W * C, height: H * C, fill: site ? '#0d1218' : '#0f141b' }));

    drawZones(map, b, f, C);
    if (site) drawFootprint(map, b, C);
    drawGrid(map, W, H, C);
    drawTracks(map, f, C, site, b);
    drawHazards(map, f, C, site, b);
    drawVictims(map, f, C, site, b);
    drawResponders(map, f, C, site, b);
  }

  function cellXY(cell, C, site, b) {
    // Returns SVG centre for a cell on the current view; projects indoor cells onto the site.
    var x = cell.x, y = cell.y;
    if (site && cell.floor !== 0) { x += (b.footprint_x || 0); y += (b.footprint_y || 0); }
    return { x: (x + 0.5) * C, y: (y + 0.5) * C };
  }

  function drawZones(map, b, f, C) {
    (b.zones || []).forEach(function (z) {
      if (z.floor !== f) return;
      var w = (z.x1 - z.x0 + 1) * C, h = (z.y1 - z.y0 + 1) * C;
      map.appendChild(svg('rect', { cls: 'zone ' + (z.kind || 'room'), x: z.x0 * C, y: z.y0 * C, width: w, height: h, rx: 1 }));
      var label = svg('text', { cls: 'zone-label ' + (z.kind || 'room'), x: z.x0 * C + 3, y: z.y0 * C + (f === 0 ? 12 : 10), text: z.name });
      map.appendChild(label);
    });
  }

  function drawFootprint(map, b, C) {
    var x = (b.footprint_x || 0) * C, y = (b.footprint_y || 0) * C;
    map.appendChild(svg('rect', { cls: 'footprint', x: x, y: y, width: b.width * C, height: b.height * C }));
    map.appendChild(svg('text', { cls: 'footprint-label', x: x + 4, y: y + b.height * C - 4, text: (b.name || 'building') + ' · ' + b.floors + ' floors' }));
  }

  function drawGrid(map, W, H, C) {
    var g = svg('g');
    for (var x = 0; x <= W; x++) g.appendChild(svg('line', { cls: 'gridline', x1: x * C, y1: 0, x2: x * C, y2: H * C }));
    for (var y = 0; y <= H; y++) g.appendChild(svg('line', { cls: 'gridline', x1: 0, y1: y * C, x2: W * C, y2: y * C }));
    map.appendChild(g);
  }

  function drawTracks(map, f, C, site, b) {
    values(S.state.responders).forEach(function (r) {
      var pts = (r.track || []).filter(function (c) { return c && c.floor === f; }).slice(-6);
      if (r.cell && r.cell.floor === f) pts.push(r.cell);
      if (pts.length < 2) return;
      var d = pts.map(function (c) { var p = cellXY(c, C, site, b); return p.x + ',' + p.y; }).join(' ');
      map.appendChild(svg('polyline', { cls: 'track', points: d }));
    });
  }

  function drawHazards(map, f, C, site, b) {
    values(S.state.hazards).forEach(function (h) {
      if (!h.active || !h.cell || h.cell.floor !== f) return;
      var p = cellXY(h.cell, C, site, b), s = site ? 8 : 11;
      var pts = p.x + ',' + (p.y - s) + ' ' + (p.x + s) + ',' + (p.y + s * 0.8) + ' ' + (p.x - s) + ',' + (p.y + s * 0.8);
      var g = svg('g', { cls: 'hazard marker' + ((h.severity || 3) >= 4 ? '' : ' minor') + (S.pulse.hazards[h.id] ? ' flash' : '') }, [
        svg('title', { text: h.kind + ' (sev ' + h.severity + ') — ' + (h.zone || '') }),
        svg('polygon', { points: pts }),
        svg('text', { x: p.x, y: p.y + s * 0.15, text: '!' })
      ]);
      map.appendChild(g);
    });
  }

  function drawVictims(map, f, C, site, b) {
    values(S.state.victims).forEach(function (v) {
      if (!v.cell || v.cell.floor !== f) return;
      var p = cellXY(v.cell, C, site, b), s = site ? 7 : 10;
      var prob = typeof v.probability === 'number' ? v.probability : 0.5;
      var opacity = v.status === 'extracted' ? 0.55 : Math.max(0.3, prob);
      var pts = p.x + ',' + (p.y - s) + ' ' + (p.x + s) + ',' + p.y + ' ' + p.x + ',' + (p.y + s) + ' ' + (p.x - s) + ',' + p.y;
      var g = svg('g', { cls: 'victim marker ' + (v.status || 'suspected') + (S.pulse.victims[v.id] ? ' flash' : ''), opacity: opacity }, [
        svg('title', { text: (v.count || 1) + ' victim(s) ' + v.status + ' p=' + prob.toFixed(2) + ' — ' + (v.zone || '') + (v.condition ? ' — ' + v.condition : '') }),
        svg('polygon', { points: pts }),
        svg('circle', { cls: 'badge-c', cx: p.x + s * 0.8, cy: p.y - s * 0.8, r: site ? 4.5 : 6 }),
        svg('text', { cls: 'badge-t', x: p.x + s * 0.8, y: p.y - s * 0.8, text: String(v.count || 1) })
      ]);
      map.appendChild(g);
    });
  }

  function drawResponders(map, f, C, site, b) {
    values(S.state.responders).forEach(function (r) {
      if (!r.cell) return;
      var projected = site && r.cell.floor !== 0;
      if (!projected && r.cell.floor !== f) return;
      var p = cellXY(r.cell, C, site, b);
      var color = STATUS_COLOR[r.status] || STATUS_COLOR.Unknown;
      var g = svg('g', { cls: 'resp marker ' + (r.status || 'Unknown') + (projected ? ' projected' : '') + (S.pulse.responders[r.id] ? ' flash' : '') }, [
        svg('title', { text: r.id + ' ' + r.name + ' (' + r.unit + ') — ' + r.status + ' — ' + (r.zone || '') + ' ' + floorLabel(r.cell.floor) + (r.air_minutes != null ? ' — air ' + r.air_minutes + ' min' : '') }),
        svg('circle', { cx: p.x, cy: p.y, r: 9, fill: color }),
        svg('text', { x: p.x, y: p.y, text: r.id })
      ]);
      if (projected) g.appendChild(svg('text', { cls: 'flr', x: p.x, y: p.y + 14, text: floorLabel(r.cell.floor) }));
      map.appendChild(g);
    });
  }

  function renderLegend() {
    var box = $('legend');
    if (box.childNodes.length) return; // static
    var items = [
      ['room', '#1b2430'], ['corridor', '#202a36'], ['stair', '#2a3442'], ['lobby', '#1f2a38'], ['outdoor', '#10171f']
    ];
    items.forEach(function (it) { box.appendChild(el('span', { cls: 'li' }, [el('span', { cls: 'sw', style: 'background:' + it[1] }), it[0]])); });
    Object.keys(STATUS_COLOR).forEach(function (k) { if (k !== 'Unknown') box.appendChild(el('span', { cls: 'li' }, [el('span', { cls: 'sw round', style: 'background:' + STATUS_COLOR[k] }), k])); });
    box.appendChild(el('span', { cls: 'li' }, [el('span', { cls: 'sw dia', style: 'background:#ffb020' }), 'victim (opacity = probability)']));
    box.appendChild(el('span', { cls: 'li' }, [el('span', { cls: 'sw tri' }), 'hazard']));
  }

  // --- responders ----------------------------------------------------------
  function renderResponders() {
    var tb = $('responders').querySelector('tbody');
    clear(tb);
    values(S.state.responders).forEach(function (r) {
      var air = r.air_minutes;
      var airCls = 'air' + (air != null && air <= 10 ? ' low' : (air != null && air <= 15 ? ' mid' : ''));
      var tr = el('tr', { cls: S.pulse.responders[r.id] ? 'changed' : '' }, [
        el('td', { cls: 'call', text: r.id }),
        el('td', { text: r.name || '', title: r.name || '' }),
        el('td', { text: r.unit || '' }),
        el('td', { cls: 'zone', title: r.zone || '' }, [el('b', { text: floorLabel(responderFloor(r)) }), ' ' + (r.zone || '—')]),
        el('td', {}, el('span', { cls: 'schip ' + (r.status || 'Unknown'), text: r.status || 'Unknown' })),
        el('td', { cls: airCls, text: air != null ? air + "'" : '—' })
      ]);
      tb.appendChild(tr);
    });
  }

  // --- briefings -----------------------------------------------------------
  function renderBriefings() {
    var box = $('briefings');
    clear(box);
    $('briefing-count').textContent = S.briefings.length ? '(' + S.briefings.length + ')' : '';
    if (!S.briefings.length) { box.appendChild(el('div', { cls: 'empty', text: 'The agent has not briefed anyone yet.' })); return; }
    S.briefings.forEach(function (b) {
      var urg = b.urgency || 'normal';
      box.appendChild(el('div', { cls: 'brief ' + urg }, [
        el('div', { cls: 'bh' }, [
          el('span', { cls: 'to', text: '→ ' + callsign(b.responder_id) }),
          el('span', { cls: 'urg', text: urg.toUpperCase() }),
          b.show_cell ? el('span', { cls: 'dim mono', text: floorLabel(b.show_cell.floor) + ' (' + b.show_cell.x + ',' + b.show_cell.y + ')' }) : null,
          el('span', { cls: 't', text: fmtTime(b.timestamp) })
        ]),
        el('div', { cls: 'txt', text: b.text || '' }),
        b.reason ? el('div', { cls: 'reason', text: b.reason }) : null
      ]));
    });
  }

  // --- assignments ---------------------------------------------------------
  function targetLabel(a) {
    if (!S.state) return a.target_id;
    if (a.target_kind === 'victim') {
      var v = S.state.victims[a.target_id];
      return v ? 'victim · ' + (v.zone || '?') + ' ' + floorLabel(v.cell && v.cell.floor) : 'victim ' + a.target_id;
    }
    if (a.target_kind === 'hazard') {
      var h = S.state.hazards[a.target_id];
      return h ? h.kind + ' · ' + (h.zone || '?') + ' ' + floorLabel(h.cell && h.cell.floor) : 'hazard ' + a.target_id;
    }
    var r = S.state.responders[a.target_id];
    return r ? callsign(r.id) + ' · ' + (r.zone || '?') + ' ' + floorLabel(responderFloor(r)) : a.target_id;
  }

  function renderAssignments() {
    var box = $('assignments');
    clear(box);
    var open = S.assignments.filter(function (a) { return a.accepted === null || a.accepted === undefined; }).length;
    $('assignment-count').textContent = S.assignments.length ? '(' + open + ' open)' : '';
    if (!S.assignments.length) { box.appendChild(el('div', { cls: 'empty', text: 'No proposals yet.' })); return; }
    S.assignments.forEach(function (a) {
      var decided = !(a.accepted === null || a.accepted === undefined);
      var cls = 'asg' + (decided ? (a.accepted ? ' accepted' : ' declined') : '');
      box.appendChild(el('div', { cls: cls }, [
        el('div', { cls: 'ah' }, [
          el('span', { cls: 'who', text: callsign(a.responder_id) }),
          el('span', { cls: 'arrow', text: '→' }),
          el('span', { cls: 'tgt', text: targetLabel(a) }),
          el('span', { cls: 't', text: fmtTime(a.timestamp) })
        ]),
        el('div', { cls: 'reason', text: a.reason || '' }),
        decided
          ? el('div', { cls: 'res', text: a.accepted ? 'ACCEPTED' : 'DECLINED' })
          : el('div', { cls: 'actions' }, [
            el('button', { cls: 'btn ok', text: 'Accept', on: { click: function () { decide(a, true, this); } } }),
            el('button', { cls: 'btn', text: 'Decline', on: { click: function () { decide(a, false, this); } } })
          ])
      ]));
    });
  }

  function decide(a, accepted, btn) {
    if (btn) btn.disabled = true;
    post('/api/assignment', { assignment_id: a.id, accepted: accepted }).then(function () {
      a.accepted = accepted;
      renderAssignments();
    }).catch(function () { if (btn) btn.disabled = false; });
  }

  // --- timeline ------------------------------------------------------------
  function renderTimeline() {
    var box = $('timeline');
    clear(box);
    var evs = (S.state.events || []).slice(-8);
    if (!evs.length) { box.appendChild(el('div', { cls: 'empty', text: 'No events.' })); return; }
    evs.forEach(function (e, i) {
      box.appendChild(el('div', { cls: 'ev ' + (e.kind || 'system') + (i === evs.length - 1 ? ' newest' : ''), title: e.text || '' }, [
        el('div', { cls: 'eh' }, [
          el('span', { cls: 'k', text: EVENT_LABEL[e.kind] || (e.kind || '').toUpperCase() }),
          e.responder_id ? el('span', { text: e.responder_id }) : null,
          el('span', { text: fmtTime(e.timestamp) })
        ]),
        el('div', { cls: 'et', text: e.text || '' })
      ]));
    });
  }

  // --- toasts --------------------------------------------------------------
  function toast(kind, head, body) {
    var box = $('toasts');
    var t = el('div', { cls: 'toast ' + kind }, [el('div', { cls: 'th', text: head }), el('div', { text: body })]);
    box.appendChild(t);
    while (box.childNodes.length > 4) box.removeChild(box.firstChild);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 6200);
  }

  // ---------------------------------------------------------------------------
  // Controls
  // ---------------------------------------------------------------------------
  function bindControls() {
    $('btn-demo-text').addEventListener('click', function () { post('/api/demo/run', { mode: 'text' }).then(function () { toast('ok', 'DEMO', 'Text scenario started'); }); });
    $('btn-demo-audio').addEventListener('click', function () { post('/api/demo/run', { mode: 'audio' }).then(function () { toast('ok', 'DEMO', 'Audio scenario started'); }); });
    $('btn-reset').addEventListener('click', function () { post('/api/demo/reset').then(function () { toast('ok', 'RESET', 'Scenario reset'); }); });
    $('btn-mic').addEventListener('click', toggleMic);
    $('btn-auto').addEventListener('click', function () { S.autoFloor = !S.autoFloor; if (S.state) renderFloorTabs(); });
    $('inject').addEventListener('submit', function (ev) { ev.preventDefault(); inject(); });
    document.addEventListener('keydown', function (ev) {
      var t = ev.target, tag = t && t.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      if (ev.key >= '0' && ev.key <= '5') { selectFloor(parseInt(ev.key, 10), true); ev.preventDefault(); }
    });
  }

  function toggleMic() {
    var btn = $('btn-mic');
    btn.disabled = true;
    var done = function () { btn.disabled = false; };
    if (!S.micOn) {
      post('/api/mic/start', { responder_id: $('mic-speaker').value || null }).then(function (res) {
        S.micOn = true;
        btn.className = 'btn mic on';
        btn.textContent = 'MIC ●';
        toast('ok', 'MIC LIVE', 'Speaking as ' + ($('mic-speaker').value || '?') + (res && res.session_id ? ' · ' + res.session_id : ''));
      }).then(done, done);
    } else {
      post('/api/mic/stop').then(function () {
        S.micOn = false;
        btn.className = 'btn mic';
        btn.textContent = 'MIC';
      }).then(done, done);
    }
  }

  function inject() {
    var input = $('inject-text');
    var text = input.value.trim();
    if (!text) return;
    var rid = $('inject-speaker').value;
    input.disabled = true;
    post('/api/report', { responder_id: rid, text: text, source: 'text' }).then(function () {
      input.value = '';
    }).then(function () { input.disabled = false; input.focus(); }, function () { input.disabled = false; });
  }

  // ---------------------------------------------------------------------------
  // Mock harness (?mock=1): no network; drives handleMessage() from an inline scenario
  // ---------------------------------------------------------------------------
  var Mock = (function () {
    // [name, floor, x0, y0, x1, y1, kind] — copied from data/scenario.json
    var Z = [
      ['command post', 0, 2, 2, 8, 6, 'outdoor'], ['staging area', 0, 10, 2, 24, 8, 'outdoor'], ['north entrance', 0, 26, 9, 33, 12, 'outdoor'],
      ['parking lot', 0, 44, 2, 58, 30, 'outdoor'], ['hydrant', 0, 12, 32, 13, 33, 'outdoor'], ['south alley', 0, 18, 29, 41, 33, 'outdoor'],
      ['engine 1 position', 0, 20, 8, 25, 11, 'outdoor'], ['ladder 2 position', 0, 34, 8, 41, 11, 'outdoor'],
      ['lobby', 1, 9, 0, 14, 4, 'lobby'], ['elevator lobby 1', 1, 10, 5, 13, 8, 'lobby'], ['stairwell A', 1, 21, 5, 23, 8, 'stair'], ['stairwell B', 1, 0, 5, 2, 8, 'stair'],
      ['east corridor 1', 1, 14, 6, 20, 7, 'corridor'], ['west corridor 1', 1, 3, 6, 9, 7, 'corridor'], ['cafe', 1, 15, 9, 23, 13, 'room'],
      ['convenience store', 1, 0, 9, 8, 13, 'room'], ['pharmacy', 1, 0, 0, 8, 4, 'room'], ['bank', 1, 15, 0, 23, 4, 'room'],
      ['elevator lobby 2', 2, 10, 5, 13, 8, 'lobby'], ['stairwell A', 2, 21, 5, 23, 8, 'stair'], ['stairwell B', 2, 0, 5, 2, 8, 'stair'],
      ['east corridor 2', 2, 14, 6, 20, 7, 'corridor'], ['west corridor 2', 2, 3, 6, 9, 7, 'corridor'], ['restaurant', 2, 3, 9, 20, 13, 'room'],
      ['gym', 2, 3, 0, 20, 4, 'room'], ['restaurant office', 2, 21, 9, 23, 13, 'room'], ['storage 2', 2, 0, 9, 2, 13, 'room'],
      ['elevator lobby 3', 3, 10, 5, 13, 8, 'lobby'], ['stairwell A', 3, 21, 5, 23, 8, 'stair'], ['stairwell B', 3, 0, 5, 2, 8, 'stair'],
      ['east corridor 3', 3, 14, 6, 20, 7, 'corridor'], ['west corridor 3', 3, 3, 6, 9, 7, 'corridor'], ['unit 301', 3, 0, 0, 8, 4, 'room'],
      ['unit 302', 3, 15, 0, 23, 4, 'room'], ['unit 303', 3, 0, 9, 8, 13, 'room'], ['unit 304', 3, 15, 9, 23, 13, 'room'],
      ['elevator lobby 4', 4, 10, 5, 13, 8, 'lobby'], ['stairwell A', 4, 21, 5, 23, 8, 'stair'], ['stairwell B', 4, 0, 5, 2, 8, 'stair'],
      ['east corridor 4', 4, 14, 6, 20, 7, 'corridor'], ['west corridor 4', 4, 3, 6, 9, 7, 'corridor'], ['unit 401', 4, 0, 0, 8, 4, 'room'],
      ['unit 402', 4, 15, 0, 23, 4, 'room'], ['unit 403', 4, 0, 9, 8, 13, 'room'], ['unit 404', 4, 15, 9, 23, 13, 'room'],
      ['elevator lobby 5', 5, 10, 5, 13, 8, 'lobby'], ['stairwell A', 5, 21, 5, 23, 8, 'stair'], ['stairwell B', 5, 0, 5, 2, 8, 'stair'],
      ['east corridor 5', 5, 14, 6, 20, 7, 'corridor'], ['west corridor 5', 5, 3, 6, 9, 7, 'corridor'], ['unit 501', 5, 0, 0, 8, 4, 'room'],
      ['unit 502', 5, 15, 0, 23, 4, 'room'], ['unit 503', 5, 0, 9, 8, 13, 'room'], ['unit 504', 5, 15, 9, 23, 13, 'room']
    ];
    var RESPONDERS = [
      ['E1-1', 'Capt. Kim Dohyun', 'Engine 1', 'attack team lead', 22, 9, 'engine 1 position'],
      ['E1-2', 'FF Park Jiwoo', 'Engine 1', 'nozzle', 23, 10, 'engine 1 position'],
      ['L2-1', 'Lt. Lee Seojin', 'Ladder 2', 'search & rescue lead', 36, 9, 'ladder 2 position'],
      ['R3-1', 'FF Choi Minjae', 'Rescue 3', 'rescue', 12, 4, 'staging area'],
      ['R3-2', 'FF Han Yuna', 'Rescue 3', 'rescue', 13, 5, 'staging area']
    ];
    // Scripted lines: text + the triage the mock would produce + side effects.
    var SCRIPT = [
      { rid: 'E1-1', text: "Command, Engine 1. We're in through the north lobby, taking stairwell A up to three. Smoke is banking down to the second floor.",
        tri: { tag: 'Status', priority: 2, summary: 'Engine 1 entering via lobby, taking stairwell A to 3', floor: 1, zone: 'stairwell A' },
        also: { 'E1-2': { zone: 'stairwell A', floor: 1 } },
        brief: [{ to: 'L2-1', text: 'Engine 1 advancing stairwell A to three. Smoke banking down to two.', urgency: 'low', reason: 'crew on same floor path' }] },
      { rid: 'L2-1', text: 'Ladder 2 to Command, starting primary search on four, west side, going up stairwell B.',
        tri: { tag: 'Status', priority: 2, summary: 'Ladder 2 starting primary search on 4 via stairwell B', floor: 4, zone: 'stairwell B' } },
      { rid: 'E1-1', text: "Engine 1 on three, east corridor. Heavy smoke, zero visibility, high heat. Fire is in 302, we're going to hit it.",
        tri: { tag: 'Danger', priority: 3, summary: 'Fire in 302, heavy smoke and heat on 3 east', floor: 3, zone: 'east corridor 3', hazards: ['heavy smoke', 'high heat'] },
        also: { 'E1-2': { zone: 'east corridor 3', floor: 3 } },
        brief: [{ to: 'L2-1', text: 'Fire apartment is 302 on three, east side. Heavy smoke and heat below you.', urgency: 'normal', reason: 'hazard one floor below search crew' }] },
      { rid: 'R3-1', text: "Rescue 3 on five via stairwell B. We've got an occupant up here saying her neighbor in 504 never came out.",
        tri: { tag: 'VictimFound', priority: 4, summary: 'Possible occupant still in 504', floor: 5, zone: 'unit 504', victim: { certainty: 'suspected', count: 1, p: 0.6, condition: 'neighbor, unknown' } },
        also: { 'R3-2': { zone: 'stairwell B', floor: 5 } },
        brief: [{ to: 'R3-1', text: 'Copy. Check 504 first, south-east corner of five. Report when you have eyes.', urgency: 'normal', reason: 'nearest crew to suspected victim' }],
        assign: [{ rid: 'R3-1', kind: 'victim', reason: 'Rescue 3-1 is already on five, 20 m from 504' }] },
      { rid: 'L2-1', text: 'Ladder 2, we hear someone yelling inside 404, the door is jammed, we need the irons up here.',
        tri: { tag: 'VictimFound', priority: 4, summary: 'Victim heard in 404, door jammed, needs irons', floor: 4, zone: 'unit 404', victim: { certainty: 'suspected', count: 1, p: 0.6 }, needs: ['irons'] },
        brief: [{ to: 'E1-2', text: 'Ladder 2 needs irons at 404, fourth floor east. Can you bring the set up stairwell A?', urgency: 'high', reason: 'closest responder with forcible entry tools' }] },
      { rid: 'E1-2', text: "Engine 1-2 to Command, found one victim in 302, adult male, unconscious. We're pulling him out to stairwell A.",
        tri: { tag: 'VictimFound', priority: 5, summary: 'Unconscious adult male found in 302, being removed', floor: 3, zone: 'unit 302', victim: { certainty: 'confirmed', count: 1, p: 0.95, condition: 'adult male, unconscious' } },
        brief: [{ to: 'E1-1', text: 'Your crew has a victim out of 302 heading to stairwell A. EMS staged at north entrance.', urgency: 'high', reason: 'crew lead needs removal path' }] },
      { rid: 'R3-2', text: "MAYDAY MAYDAY MAYDAY. Rescue 3-2, fifth floor, stairwell B landing. The ceiling came down, Choi is pinned under it, I can't move him. We need the RIT up here now.",
        tri: { tag: 'Danger', priority: 5, summary: 'MAYDAY: ceiling collapse stairwell B on 5, R3-1 pinned', floor: 5, zone: 'stairwell B', status: 'NeedsHelp', hazards: ['ceiling collapse'], needs: ['RIT'], mayday: true },
        also: { 'R3-1': { status: 'InDanger', zone: 'stairwell B', floor: 5 } },
        brief: [
          { to: 'L2-1', text: 'MAYDAY on five, stairwell B landing, collapse, Choi pinned. You are closest. Go up B now.', urgency: 'critical', reason: 'nearest crew, one floor below the mayday' },
          { to: 'E1-1', text: 'MAYDAY stairwell B fifth floor, ceiling collapse. RIT activating. Keep stairwell A open for egress.', urgency: 'critical', reason: 'same building, egress route affected' },
          { to: 'R3-2', text: 'Command copies your mayday. RIT and Ladder 2 coming up stairwell B. Stay on air.', urgency: 'critical', reason: 'mayday receipt confirmation' }
        ],
        assign: [{ rid: 'L2-1', kind: 'responder', target: 'R3-1', reason: 'Ladder 2 is one floor below the collapse on stairwell B' }] },
      { rid: 'L2-1', text: 'Ladder 2, we forced 404. Two victims, a woman and a child, both responsive. Taking them down — Command, is stairwell B clear? We heard a collapse above us.',
        tri: { tag: 'VictimFound', priority: 5, summary: 'Two responsive victims in 404, crew asking if stairwell B is clear', floor: 4, zone: 'unit 404', victim: { certainty: 'confirmed', count: 2, p: 0.95, condition: 'woman and child, responsive' } },
        brief: [{ to: 'L2-1', text: 'Stairwell B is NOT clear above four. Take your two victims down stairwell A, east side.', urgency: 'critical', reason: 'egress route blocked by collapse' }] },
      { rid: 'E1-1', text: "Engine 1, low air alarm on 1-2. We're backing out down stairwell A with the victim. Send a relief crew to three to hold the line.",
        tri: { tag: 'Danger', priority: 4, summary: 'Low air on E1-2, Engine 1 backing out, relief crew needed on 3', floor: 3, zone: 'stairwell A', status: 'Evacuating', needs: ['relief crew'] },
        also: { 'E1-2': { status: 'Evacuating', air: 8, zone: 'stairwell A', floor: 3 } },
        brief: [{ to: 'R3-2', text: 'Relief needed on three at 302 once RIT has you. Engine 1 is backing out low on air.', urgency: 'normal', reason: 'resource request' }] },
      { rid: 'R3-1', text: "Rescue 3-1 to Command. RIT got the beam off me, I'm okay, I can walk. We're coming down stairwell A, not B. B is blocked at five.",
        tri: { tag: 'Status', priority: 3, summary: 'R3-1 freed and walking, stairwell B blocked at 5', floor: 5, zone: 'stairwell A', status: 'OK', hazards: ['stairwell blocked'] },
        also: { 'R3-2': { status: 'OK', zone: 'stairwell A', floor: 5 } },
        brief: [{ to: 'L2-1', text: 'Rescue 3 is free and walking out via stairwell A. B remains blocked at five.', urgency: 'normal', reason: 'closing the mayday for responding crew' }] },
      { rid: 'L2-1', text: 'Ladder 2 out the north entrance with two victims, handing off to EMS at staging.',
        tri: { tag: 'Status', priority: 2, summary: 'Ladder 2 out with two victims, handing to EMS', floor: 0, zone: 'north entrance', victim: { certainty: 'extracted', count: 2, p: 0.95, from: 'unit 404', fromFloor: 4 } } },
      { rid: 'E1-1', text: "Engine 1 at the lobby, victim handed to EMS. We're going to rehab. 302 is knocked down, but nobody has checked 303 yet.",
        tri: { tag: 'Status', priority: 3, summary: '302 knocked down, victim to EMS, 303 unchecked', floor: 1, zone: 'lobby', status: 'OK', victim: { certainty: 'extracted', count: 1, p: 0.95, from: 'unit 302', fromFloor: 3 } },
        also: { 'E1-2': { status: 'OK', zone: 'lobby', floor: 1 } },
        brief: [{ to: 'R3-2', text: 'Unit 303 on three is unchecked. When you are relieved, primary search 303 west side.', urgency: 'normal', reason: 'open search area' }] }
    ];

    var st = null, seq = 0, timers = [], running = false;

    function id(prefix) { return prefix + '_' + (++seq).toString(36) + Math.random().toString(36).slice(2, 8); }
    function now() { return new Date().toISOString(); }
    function zoneRec(z) { return { name: z[0], floor: z[1], x0: z[2], y0: z[3], x1: z[4], y1: z[5], aliases: [], kind: z[6] }; }
    function findZone(name, floor) {
      var hit = null;
      Z.forEach(function (z) { if (z[0] === name && (floor === undefined || floor === null || z[1] === floor)) hit = hit || z; });
      return hit ? zoneRec(hit) : null;
    }
    function center(z) { return { floor: z.floor, x: Math.floor((z.x0 + z.x1) / 2), y: Math.floor((z.y0 + z.y1) / 2) }; }

    function initial() {
      var responders = {};
      RESPONDERS.forEach(function (r) {
        responders[r[0]] = { id: r[0], name: r[1], unit: r[2], role: r[3], status: 'OK', cell: { floor: 0, x: r[4], y: r[5] }, zone: r[6], air_minutes: 30, last_report_id: null, last_seen: now(), track: [] };
      });
      return {
        version: 0,
        incident_name: 'Structure fire — Hanul Tower, 5-story mixed-use (retail 1-2F, residential 3-5F)',
        building: { name: 'Hanul Tower', address: '27 Seongsu-ro, Seongdong-gu, Seoul (fictional)', floors: 5, width: 24, height: 14, geo_origin: { lat: 37.5448, lon: 127.0557 }, meters_per_cell: 1.5, bearing_deg: 0, site_width: 60, site_height: 40, footprint_x: 18, footprint_y: 13, zones: Z.map(zoneRec) },
        responders: responders, victims: {}, hazards: {}, queue: [],
        events: [{ id: id('evt'), kind: 'system', responder_id: null, text: 'Mock scenario loaded (?mock=1) — no server', ref_id: null, timestamp: now() }],
        updated_at: now()
      };
    }

    function snapshot() { st.updated_at = now(); return JSON.parse(JSON.stringify(st)); }
    function emit(type, payload) { handleMessage({ type: type, payload: payload }); }

    function moveResponder(r, zoneName, floor, delta) {
      var z = findZone(zoneName, floor);
      if (z) { if (r.cell) r.track.push(r.cell); r.track = r.track.slice(-8); r.cell = center(z); r.zone = z.name; }
      r.last_seen = now();
      if (delta.changed_responders.indexOf(r.id) < 0) delta.changed_responders.push(r.id);
    }

    function applyVictim(tri, report, delta) {
      var v = tri.victim; if (!v || v.certainty === 'none') return;
      if (v.certainty === 'extracted') {
        var zn = v.from || tri.zone, fl = v.fromFloor != null ? v.fromFloor : tri.floor;
        values(st.victims).forEach(function (x) { if (x.zone === zn && x.cell.floor === fl && x.status !== 'extracted') { x.status = 'extracted'; x.updated_at = now(); x.source_report_ids.push(report.id); delta.changed_victims.push(x.id); } });
        return;
      }
      var z = findZone(tri.zone, tri.floor); if (!z) return;
      var existing = null;
      values(st.victims).forEach(function (x) { if (x.zone === z.name && x.cell.floor === z.floor && x.status !== 'extracted') existing = x; });
      if (existing) {
        existing.probability = Math.max(existing.probability, v.p); existing.count = Math.max(existing.count, v.count);
        existing.status = v.certainty; existing.condition = v.condition || existing.condition; existing.source = 'fused';
        existing.source_report_ids.push(report.id); existing.updated_at = now(); delta.changed_victims.push(existing.id);
      } else {
        var nv = { id: id('vic'), cell: center(z), zone: z.name, probability: v.p, status: v.certainty, count: v.count, condition: v.condition || null, source_report_ids: [report.id], source: 'radio', assigned_responder_id: null, created_at: now(), updated_at: now() };
        st.victims[nv.id] = nv; delta.changed_victims.push(nv.id);
      }
    }

    function applyHazards(tri, report, delta) {
      (tri.hazards || []).forEach(function (kind) {
        var z = findZone(tri.zone, tri.floor); if (!z) return;
        var sev = /collapse|blocked|flashover|low air/.test(kind) ? 5 : 3;
        var h = { id: id('haz'), kind: kind, cell: center(z), zone: z.name, severity: sev, source_report_ids: [report.id], active: true, created_at: now() };
        st.hazards[h.id] = h; delta.changed_hazards.push(h.id);
      });
    }

    function score(q) {
      var tri = q.triage, ageMin = (Date.now() - Date.parse(q.report.timestamp)) / 60000;
      return (q.acknowledged ? -1000 : 0) + tri.priority * 10 + (tri.mayday ? 20 : 0) + Math.max(0, 10 - ageMin);
    }
    function resortQueue() { st.queue.forEach(function (q) { q.score = score(q); }); st.queue.sort(function (a, b) { return b.score - a.score; }); }

    function applyReport(rid, text, tri, also, source) {
      st.version++;
      var report = { id: id('rpt'), responder_id: rid, speaker_label: null, transcript: text, language: 'en', audio_path: null, source: source || 'scripted', timestamp: now() };
      var triage = {
        report_id: report.id, responder_id: rid, tag: tri.tag, priority: tri.priority, summary: tri.summary, floor: tri.floor == null ? null : tri.floor, zone: tri.zone || null,
        responder_status: tri.status || (tri.mayday ? 'InDanger' : 'Unknown'), victim_count: tri.victim ? tri.victim.count : 0, victim_condition: tri.victim ? (tri.victim.condition || null) : null,
        victim_certainty: tri.victim ? tri.victim.certainty : 'none', hazards: tri.hazards || [], needs: tri.needs || [], mayday: !!tri.mayday, confidence: 0.9, model: 'mock', latency_ms: 120, timestamp: now()
      };
      var delta = { version: st.version, triage: triage, touch: null, detections: [], changed_responders: [], changed_victims: [], changed_hazards: [], new_events: [], timestamp: now() };
      var r = st.responders[rid];
      if (r) {
        moveResponder(r, tri.zone, tri.floor, delta);
        if (tri.status) r.status = tri.status;
        r.last_report_id = report.id;
      }
      Object.keys(also || {}).forEach(function (oid) {
        var o = st.responders[oid], ch = also[oid]; if (!o) return;
        if (ch.zone) moveResponder(o, ch.zone, ch.floor, delta);
        if (ch.status) o.status = ch.status;
        if (ch.air != null) o.air_minutes = ch.air;
        if (delta.changed_responders.indexOf(oid) < 0) delta.changed_responders.push(oid);
      });
      applyVictim(tri, report, delta);
      applyHazards(tri, report, delta);
      st.queue.push({ triage: triage, report: report, acknowledged: false, score: 0 });
      resortQueue();
      delta.new_events.push({ id: id('evt'), kind: 'report', responder_id: rid, text: text, ref_id: report.id, timestamp: now() });
      delta.new_events.push({ id: id('evt'), kind: 'triage', responder_id: rid, text: '[' + tri.tag + ' P' + tri.priority + '] ' + tri.summary, ref_id: report.id, timestamp: now() });
      st.events = st.events.concat(delta.new_events);
      return { report: report, triage: triage, delta: delta };
    }

    function victimIn(zoneName, floor) {
      var hit = null;
      values(st.victims).forEach(function (v) { if (v.zone === zoneName && v.cell.floor === floor && v.status !== 'extracted') hit = v; });
      return hit;
    }

    function runStep(step) {
      var half = step.text.slice(0, Math.floor(step.text.length / 2));
      emit('transcript', { text: half, final: false, speaker: null, responder_id: step.rid });
      later(900, function () { emit('transcript', { text: step.text, final: true, speaker: null, responder_id: step.rid }); });
      later(1300, function () {
        var out = applyReport(step.rid, step.text, step.tri, step.also, 'scripted');
        emit('delta', out.delta);
        emit('state', snapshot());
        (step.brief || []).forEach(function (b, i) {
          later(900 + i * 400, function () {
            var ev = { id: id('evt'), kind: 'briefing', responder_id: b.to, text: b.text, ref_id: out.report.id, timestamp: now() };
            st.events.push(ev);
            emit('briefing', { id: id('brf'), responder_id: b.to, text: b.text, urgency: b.urgency, reason: b.reason, trigger_ids: [out.report.id], show_cell: step.tri.zone ? center(findZone(step.tri.zone, step.tri.floor) || { floor: 0, x0: 0, y0: 0, x1: 0, y1: 0 }) : null, timestamp: now() });
            emit('event', ev);
          });
        });
        (step.assign || []).forEach(function (a, i) {
          later(1800 + i * 300, function () {
            var target = a.target || (a.kind === 'victim' ? (victimIn(step.tri.zone, step.tri.floor) || {}).id : null);
            if (!target) return;
            emit('assignment', { id: id('asg'), responder_id: a.rid, target_kind: a.kind, target_id: target, reason: a.reason, accepted: null, timestamp: now() });
          });
        });
      });
    }

    function later(ms, fn) { timers.push(setTimeout(fn, ms)); }
    function stopTimers() { timers.forEach(clearTimeout); timers = []; running = false; }

    function run(speed) {
      stopTimers();
      running = true;
      var gap = 5200 / (speed || 1);
      SCRIPT.forEach(function (step, i) { later(500 + i * gap, function () { runStep(step); }); });
      later(500 + SCRIPT.length * gap, function () { running = false; });
    }

    function reset() {
      stopTimers();
      st = initial();
      emit('state', snapshot());
    }

    // Keyword triage for lines typed into the inject box while mocked.
    function keywordTriage(text) {
      var t = text.toLowerCase();
      var tri = { tag: 'Status', priority: 2, summary: text.length > 60 ? text.slice(0, 57) + '…' : text, floor: null, zone: null };
      var fm = t.match(/\b(?:floor|on) (\d)\b/) || t.match(/\b(\d)(?:st|nd|rd|th) floor\b/) || t.match(/\b([1-5])0[1-9]\b/);
      if (fm) tri.floor = parseInt(fm[1], 10);
      Z.forEach(function (z) { if (!tri.zone && t.indexOf(z[0]) >= 0) { tri.zone = z[0]; if (tri.floor == null) tri.floor = z[1]; } });
      var um = t.match(/\b([1-5]0[1-9])\b/); if (um && !tri.zone) { tri.zone = 'unit ' + um[1]; tri.floor = parseInt(um[1][0], 10); }
      if (/mayday/.test(t)) { tri.tag = 'Danger'; tri.priority = 5; tri.mayday = true; tri.status = 'InDanger'; }
      else if (/collapse|trapped|low air|flashover|pinned|lost/.test(t)) { tri.tag = 'Danger'; tri.priority = 4; tri.hazards = ['reported hazard']; }
      else if (/victim|occupant|person|kid|child|someone|unconscious/.test(t)) { tri.tag = 'VictimFound'; tri.priority = 4; tri.victim = { certainty: /found|eyes on|got a|unconscious|breathing/.test(t) ? 'confirmed' : 'suspected', count: /two|2/.test(t) ? 2 : 1, p: /found|eyes on|got a/.test(t) ? 0.95 : 0.6 }; }
      else if (/need|send|request|water|relief/.test(t)) { tri.tag = 'HelpNeeded'; tri.priority = 3; tri.needs = ['requested']; }
      if (/okay|ok|good|i'm fine/.test(t) && tri.tag === 'Status') tri.status = 'OK';
      return tri;
    }

    function handlePost(path, body) {
      return new Promise(function (resolve) {
        setTimeout(function () {
          if (path === '/api/demo/run') { run(body.speed); resolve({ started: true }); }
          else if (path === '/api/demo/reset') { reset(); resolve({ ok: true }); }
          else if (path === '/api/ack') {
            st.queue.forEach(function (q) { if (q.report.id === body.report_id) q.acknowledged = true; });
            st.version++; resortQueue(); emit('state', snapshot()); resolve({ ok: true });
          }
          else if (path === '/api/assignment') { resolve({ ok: true }); }
          else if (path === '/api/mic/start') { resolve({ session_id: 'mock-mic' }); }
          else if (path === '/api/mic/stop') { resolve({ ok: true }); }
          else if (path === '/api/report') {
            var tri = keywordTriage(body.text);
            emit('transcript', { text: body.text, final: true, speaker: null, responder_id: body.responder_id });
            var out = applyReport(body.responder_id, body.text, tri, null, 'text');
            emit('delta', out.delta); emit('state', snapshot());
            resolve({ report: out.report, triage: out.triage, delta: out.delta });
          }
          else resolve({ ok: true });
        }, 120);
      });
    }

    function start() {
      st = initial();
      emit('state', snapshot());
      setConn(true);
      $('conn').textContent = 'MOCK';
      $('conn').title = 'Mock harness — no server';
      setTimeout(function () { run(1); }, 1500);
    }

    return { start: start, handlePost: handlePost, isRunning: function () { return running; } };
  })();

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------
  function boot() {
    bindControls();
    setInterval(function () { $('clock').textContent = fmtClock(new Date()); }, 1000);
    $('clock').textContent = fmtClock(new Date());
    setInterval(tickAges, 1000);
    fetchHealth();
    if (MOCK) { Mock.start(); return; }
    api('/api/state').then(function (st) { if (st && st.building) handleMessage({ type: 'state', payload: st }); }).catch(function () {});
    connect();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

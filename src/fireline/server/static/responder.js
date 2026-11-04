/* Fireline responder clip-on display.
 *
 * Served at /responder/{id}. Consumes the contract in docs/CONTRACT.md:
 *   GET  /api/state            -> WorldState (initial render + reconnect fallback)
 *   WS   /ws                   -> state / delta / briefing / transcript / event / assignment
 *   POST /api/touch            -> TouchInput {responder_id, action, cell}
 *   POST /api/photo            -> {responder_id, image_b64, mime} => {detections, delta, latency_ms}
 *   GET  /samples/<name>.jpg   -> sample helmet-cam frames (demo without a camera)
 *
 * Dev harness: open with ?mock=1 (works from file://) and the UI is driven by an
 * inline fake state generator instead of the network.
 */
(function () {
  'use strict';

  // ------------------------------------------------------------------ config
  // ?mock=1 drives the UI from the inline harness; a page opened without a server
  // (file:// or a data: snapshot) can only ever be mock, so treat it the same way.
  var MOCK = /(?:^|[?&])mock=1(?:&|$)/.test(location.search) ||
    location.protocol === 'file:' || location.protocol === 'data:';
  var SAMPLE_NAMES = ['smoky_room_victim', 'corridor_clear', 'two_victims_404'];
  var NEARBY_CELLS = 8;
  var MAP_PX_W = 336;
  var PHOTO_MAX = 1024;
  var PHOTO_SHOW_MS = 6000;

  var STATUS_COLOR = {
    OK: '#3ddc84', InDanger: '#ff3b3b', NeedsHelp: '#4f9cff', Evacuating: '#ffb020', Unknown: '#6c7a89'
  };
  var STATUS_LABEL = {
    OK: 'OK', InDanger: 'IN DANGER', NeedsHelp: 'NEEDS HELP', Evacuating: 'EVACUATING', Unknown: 'UNKNOWN'
  };
  var ZONE_FILL = {
    room: '#1b2430', corridor: '#202a36', stair: '#2a3442', lobby: '#1f2a38', outdoor: '#10171f', roof: '#1b2430'
  };

  var $ = function (id) { return document.getElementById(id); };
  var SVG_NS = 'http://www.w3.org/2000/svg';
  var userTapped = false;   // vibrate() is only allowed after a user gesture
  document.addEventListener('pointerdown', function () { userTapped = true; }, { capture: true, once: true });

  // ------------------------------------------------------------------- state
  var app = {
    id: parseResponderId(),
    state: null,          // last full WorldState snapshot
    me: null,             // my Responder from state
    floor: null,          // floor currently drawn
    briefings: [],        // Briefing objects for me, newest first
    unread: [],           // briefing ids not yet shown/spoken
    current: null,        // Briefing shown in the card
    muted: loadPref('fireline.muted', false),
    audioEnabled: false,
    markMode: false,
    markCell: null,
    showCell: null,       // Briefing.show_cell to highlight
    pendingVictims: [],   // ids from the last delta, resolved on next state
    pendingHazards: [],
    ws: null,
    backoff: 1000,
    connected: false
  };

  // ------------------------------------------------------------- utilities
  /** /responder/{id} -> id; otherwise ?id=..., else the demo default "L2-1". */
  function parseResponderId() {
    var q = /(?:^|[?&])id=([^&]+)/.exec(location.search);
    if (q) return decodeURIComponent(q[1]);
    if (!/^https?:$/.test(location.protocol)) return 'L2-1';
    var parts = location.pathname.split('/').filter(Boolean);
    var last = parts.length ? decodeURIComponent(parts[parts.length - 1]) : '';
    if (!last || /\.html?$/i.test(last) || last.toLowerCase() === 'responder' || last.length > 32) return 'L2-1';
    return last;
  }

  function loadPref(key, fallback) {
    try {
      var v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch (e) { return fallback; }
  }
  function savePref(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }

  function ago(iso) {
    if (!iso) return '';
    var ms = Date.now() - new Date(iso).getTime();
    if (!isFinite(ms) || ms < 0) ms = 0;
    var s = Math.round(ms / 1000);
    if (s < 5) return 'just now';
    if (s < 60) return s + 's ago';
    var m = Math.floor(s / 60);
    if (m < 60) return m + 'm ago';
    return Math.floor(m / 60) + 'h ago';
  }

  function cellDist(a, b) {
    return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y));
  }

  function zoneAt(cell) {
    if (!cell || !app.state) return null;
    var zones = app.state.building.zones || [];
    for (var i = 0; i < zones.length; i++) {
      var z = zones[i];
      if (z.floor === cell.floor && z.x0 <= cell.x && cell.x <= z.x1 && z.y0 <= cell.y && cell.y <= z.y1) return z;
    }
    return null;
  }

  function zoneByName(name) {
    if (!name || !app.state) return null;
    var key = String(name).toLowerCase();
    var zones = app.state.building.zones || [];
    for (var i = 0; i < zones.length; i++) if (zones[i].name.toLowerCase() === key) return zones[i];
    return null;
  }

  function values(obj) {
    if (!obj) return [];
    if (Array.isArray(obj)) return obj;
    return Object.keys(obj).map(function (k) { return obj[k]; });
  }

  function floorLabel(f) { return f === 0 ? 'SITE' : 'FLOOR ' + f; }

  function svgEl(tag, attrs, text) {
    var el = document.createElementNS(SVG_NS, tag);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) el.setAttribute(k, attrs[k]);
    if (text !== undefined) el.textContent = text;
    return el;
  }

  // --------------------------------------------------------------- toasts
  function toast(text, kind, ms) {
    var box = $('toasts');
    var el = document.createElement('div');
    el.className = 'toast ' + (kind || '');
    el.textContent = text;
    box.appendChild(el);
    while (box.children.length > 2) box.removeChild(box.firstChild);
    setTimeout(function () { el.classList.add('out'); }, (ms || 3500) - 400);
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, ms || 3500);
  }

  // ----------------------------------------------------------------- speech
  var speech = {
    voice: null,
    queue: [],
    speaking: false,

    supported: function () { return typeof window.speechSynthesis !== 'undefined' && typeof window.SpeechSynthesisUtterance !== 'undefined'; },

    pickVoice: function () {
      if (!this.supported()) return;
      try {
        var vs = window.speechSynthesis.getVoices() || [];
        var en = vs.filter(function (v) { return /^en/i.test(v.lang); });
        var pref = en.filter(function (v) { return /^en[-_]US/i.test(v.lang); });
        this.voice = pref[0] || en[0] || null;
      } catch (e) { this.voice = null; }
    },

    /** Unlock audio with a user gesture, then drain whatever is queued. */
    enable: function () {
      app.audioEnabled = true;
      if (!this.supported()) return;
      this.pickVoice();
      try { window.speechSynthesis.cancel(); } catch (e) { /* ignore */ }
      this.say('Fireline audio on.', true);
    },

    say: function (text, bypassMute) {
      if (!app.audioEnabled || !this.supported()) return;
      if (app.muted && !bypassMute) return;
      this.queue.push(text);
      this.drain();
    },

    drain: function () {
      var self = this;
      if (self.speaking || !self.queue.length) return;
      if (app.muted) { self.queue = []; return; }
      var text = self.queue.shift();
      try {
        var u = new SpeechSynthesisUtterance(text);
        u.rate = 1.05;
        u.lang = 'en-US';
        if (self.voice) u.voice = self.voice;
        var done = function () { self.speaking = false; setTimeout(function () { self.drain(); }, 150); };
        u.onend = done;
        u.onerror = done;
        self.speaking = true;
        window.speechSynthesis.speak(u);
        // safety: some engines never fire onend
        setTimeout(function () { if (self.speaking) done(); }, 15000);
      } catch (e) {
        self.speaking = false;
      }
    },

    stop: function () {
      this.queue = [];
      this.speaking = false;
      if (this.supported()) { try { window.speechSynthesis.cancel(); } catch (e) { /* ignore */ } }
    }
  };
  if (speech.supported()) {
    try { window.speechSynthesis.onvoiceschanged = function () { speech.pickVoice(); }; } catch (e) { /* ignore */ }
  }

  // -------------------------------------------------------------- render
  function render() {
    if (!app.state) return;
    app.me = (app.state.responders && app.state.responders[app.id]) || null;
    app.floor = currentFloor();
    renderBanner();
    renderBriefing();
    renderMap();
    renderButtons();
  }

  function currentFloor() {
    if (app.me && app.me.cell) return app.me.cell.floor;
    var z = app.me && zoneByName(app.me.zone);
    if (z) return z.floor;
    return app.floor === null ? 0 : app.floor;
  }

  function renderBanner() {
    var me = app.me;
    var banner = $('banner');
    var status = (me && me.status) || 'Unknown';
    banner.className = 'banner status-' + status.toLowerCase();
    $('callsign').textContent = me ? me.id : app.id;
    $('statusPill').textContent = STATUS_LABEL[status] || status.toUpperCase();
    $('unit').textContent = me ? (me.unit + (me.name ? ' · ' + me.name : '')) : 'not on roster';

    var air = $('air');
    if (me && me.air_minutes !== null && me.air_minutes !== undefined) {
      air.textContent = 'AIR ' + me.air_minutes + ' MIN';
      air.className = 'air mono' + (me.air_minutes <= 5 ? ' critical' : me.air_minutes <= 10 ? ' low' : '');
    } else {
      air.textContent = 'AIR --';
      air.className = 'air mono';
    }

    var z = me && (zoneByName(me.zone) || zoneAt(me.cell));
    var loc = me && me.cell ? floorLabel(me.cell.floor) : floorLabel(app.floor);
    if (z) loc += ' · ' + z.name.toUpperCase();
    else if (me && me.zone) loc += ' · ' + String(me.zone).toUpperCase();
    $('loc').textContent = loc;
  }

  function renderBriefing() {
    var card = $('briefing');
    var b = app.current;
    var text = $('briefingText');
    if (!b) {
      card.className = 'briefing urgency-normal';
      text.className = 'briefing-text empty';
      text.textContent = app.briefings.length ? 'Tap UNREAD to read.' : 'Waiting for command…';
      $('briefingLabel').textContent = 'BRIEFING';
      $('briefingAgo').textContent = '';
    } else {
      card.className = 'briefing urgency-' + (b.urgency || 'normal');
      text.className = 'briefing-text';
      text.textContent = b.text;
      $('briefingLabel').textContent = String(b.urgency || 'normal').toUpperCase();
      $('briefingAgo').textContent = ago(b.timestamp);
    }
    var ub = $('unreadBtn');
    ub.hidden = app.unread.length === 0;
    ub.textContent = app.unread.length + ' UNREAD';
    var mb = $('muteBtn');
    mb.className = 'mute' + (app.muted ? ' on' : '');
    mb.innerHTML = app.muted ? '&#128263;' : '&#128266;';
  }

  function mapGeom(floor) {
    var b = app.state.building;
    var w = floor === 0 ? (b.site_width || 60) : b.width;
    var h = floor === 0 ? (b.site_height || 40) : b.height;
    var cs = MAP_PX_W / w;
    return { w: w, h: h, cs: cs, W: w * cs, H: h * cs };
  }

  function renderMap() {
    if (!app.state) return; // a briefing or tap can race the first snapshot
    var svg = $('map');
    var floor = app.floor;
    var g = mapGeom(floor);
    var b = app.state.building;
    svg.setAttribute('viewBox', '0 0 ' + g.W + ' ' + g.H);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.className.baseVal = 'map' + (app.markMode ? ' marking' : '');

    $('mapFloor').textContent = floorLabel(floor) + ' · ' + (b.name || '');
    $('mapHint').textContent = app.markMode ? 'TAP CELL TO MARK' : '';

    // background + zones
    svg.appendChild(svgEl('rect', { x: 0, y: 0, width: g.W, height: g.H, fill: floor === 0 ? '#0d1218' : '#0f141b' }));
    var zones = svgEl('g', { 'class': 'zone' });
    (b.zones || []).forEach(function (z) {
      if (z.floor !== floor) return;
      var x = z.x0 * g.cs, y = z.y0 * g.cs, w = (z.x1 - z.x0 + 1) * g.cs, h = (z.y1 - z.y0 + 1) * g.cs;
      zones.appendChild(svgEl('rect', { x: x, y: y, width: w, height: h, fill: ZONE_FILL[z.kind] || ZONE_FILL.room, rx: 1.5 }));
      var label = z.name.length > 14 ? z.name.slice(0, 13) + '…' : z.name;
      zones.appendChild(svgEl('text', { x: x + 2, y: y + 8.5 }, label));
    });
    svg.appendChild(zones);

    if (floor === 0) {
      svg.appendChild(svgEl('rect', {
        'class': 'footprint',
        x: (b.footprint_x || 0) * g.cs, y: (b.footprint_y || 0) * g.cs,
        width: b.width * g.cs, height: b.height * g.cs
      }));
    }

    // grid
    var grid = svgEl('g', { 'class': 'grid' });
    var step = floor === 0 ? 5 : 1;
    for (var gx = 0; gx <= g.w; gx += step) grid.appendChild(svgEl('line', { x1: gx * g.cs, y1: 0, x2: gx * g.cs, y2: g.H }));
    for (var gy = 0; gy <= g.h; gy += step) grid.appendChild(svgEl('line', { x1: 0, y1: gy * g.cs, x2: g.W, y2: gy * g.cs }));
    svg.appendChild(grid);

    // briefing highlight cell
    if (app.showCell && app.showCell.floor === floor) {
      svg.appendChild(svgEl('rect', {
        'class': 'show-cell', rx: 2,
        x: (app.showCell.x - 1) * g.cs, y: (app.showCell.y - 1) * g.cs, width: 3 * g.cs, height: 3 * g.cs
      }));
    }

    // mark-mode selection
    if (app.markMode && app.markCell && app.markCell.floor === floor) {
      svg.appendChild(svgEl('rect', {
        'class': 'mark-cell', x: app.markCell.x * g.cs, y: app.markCell.y * g.cs, width: g.cs, height: g.cs
      }));
    }

    drawHazards(svg, g, floor);
    drawVictims(svg, g, floor);
    drawResponders(svg, g, floor);

    // transparent hit layer for mark mode
    var hit = svgEl('rect', { 'class': 'hit', x: 0, y: 0, width: g.W, height: g.H });
    svg.appendChild(hit);
  }

  function drawHazards(svg, g, floor) {
    values(app.state.hazards).forEach(function (h) {
      if (!h.active || !h.cell || h.cell.floor !== floor) return;
      var cx = (h.cell.x + 0.5) * g.cs, cy = (h.cell.y + 0.5) * g.cs, r = Math.max(7, g.cs * 0.7);
      var grp = svgEl('g', { 'class': 'hazard pulse' });
      var pts = [cx, cy - r, cx + r, cy + r * 0.8, cx - r, cy + r * 0.8].join(' ');
      grp.appendChild(svgEl('polygon', { points: pts }));
      grp.appendChild(svgEl('text', { x: cx, y: cy + r * 0.15 }, '!'));
      grp.appendChild(svgEl('title', {}, h.kind));
      svg.appendChild(grp);
    });
  }

  function drawVictims(svg, g, floor) {
    var myCell = app.me && app.me.cell;
    values(app.state.victims).forEach(function (v) {
      if (!v.cell || v.cell.floor !== floor) return;
      // victims within NEARBY_CELLS get the full marker; farther ones on this floor are faint ghosts
      var far = !!(myCell && myCell.floor === floor && cellDist(myCell, v.cell) > NEARBY_CELLS);
      var cx = (v.cell.x + 0.5) * g.cs, cy = (v.cell.y + 0.5) * g.cs, r = far ? Math.max(5, g.cs * 0.5) : Math.max(8, g.cs * 0.8);
      var opacity = far ? 0.22 : Math.max(0.35, Math.min(1, v.probability || 0));
      var grp = svgEl('g', { 'class': 'victim ' + (v.status || '') + (far ? ' far' : ''), opacity: opacity });
      var pts = [cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy].join(' ');
      grp.appendChild(svgEl('polygon', { 'class': 'marker', points: pts }));
      if (!far) {
        grp.appendChild(svgEl('text', { 'class': 'badge', x: cx, y: cy }, String(v.count || 1)));
        grp.appendChild(svgEl('text', { 'class': 'prob', x: cx, y: cy + r + 7 }, Math.round((v.probability || 0) * 100) + '%'));
      }
      grp.appendChild(svgEl('title', {}, (v.status || 'suspected') + ' · ' + (v.zone || '')));
      svg.appendChild(grp);
    });
  }

  function drawResponders(svg, g, floor) {
    values(app.state.responders).forEach(function (r) {
      if (!r.cell || r.cell.floor !== floor || r.id === app.id) return;
      var cx = (r.cell.x + 0.5) * g.cs, cy = (r.cell.y + 0.5) * g.cs;
      var grp = svgEl('g', { 'class': 'other' });
      grp.appendChild(svgEl('circle', { cx: cx, cy: cy, r: 6, fill: STATUS_COLOR[r.status] || STATUS_COLOR.Unknown }));
      grp.appendChild(svgEl('text', { x: cx, y: cy - 8 }, r.id));
      svg.appendChild(grp);
    });
    var me = app.me;
    if (me && me.cell && me.cell.floor === floor) {
      var mx = (me.cell.x + 0.5) * g.cs, my = (me.cell.y + 0.5) * g.cs;
      var grp2 = svgEl('g', { 'class': 'me' + (me.status === 'InDanger' ? ' pulse' : '') });
      grp2.appendChild(svgEl('circle', { cx: mx, cy: my, r: 22, fill: STATUS_COLOR[me.status] || STATUS_COLOR.Unknown, opacity: 0.18, stroke: 'none' }));
      grp2.appendChild(svgEl('circle', { cx: mx, cy: my, r: 13, fill: STATUS_COLOR[me.status] || STATUS_COLOR.Unknown }));
      grp2.appendChild(svgEl('text', { x: mx, y: my }, me.id));
      svg.appendChild(grp2);
    }
  }

  function renderButtons() {
    $('buttons').hidden = app.markMode;
    $('markButtons').hidden = !app.markMode;
    $('btnConfirm').disabled = !(app.markCell);
    $('btnConfirm').textContent = app.markCell ? 'CONFIRM HERE' : 'TAP A CELL';
  }

  // ------------------------------------------------------- map tapping
  function svgPoint(svg, evt) {
    var pt = svg.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    var ctm = svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }

  function onMapTap(evt) {
    if (!app.markMode || !app.state) return;
    var svg = $('map');
    var p = svgPoint(svg, evt);
    if (!p) return;
    var g = mapGeom(app.floor);
    var x = Math.max(0, Math.min(g.w - 1, Math.floor(p.x / g.cs)));
    var y = Math.max(0, Math.min(g.h - 1, Math.floor(p.y / g.cs)));
    app.markCell = { floor: app.floor, x: x, y: y };
    renderMap();
    renderButtons();
  }

  // --------------------------------------------------------- messages
  function handleMessage(msg) {
    if (!msg || !msg.type) return;
    switch (msg.type) {
      case 'state': onState(msg.payload); break;
      case 'delta': onDelta(msg.payload); break;
      case 'briefing': onBriefing(msg.payload); break;
      case 'transcript': onTranscript(msg.payload); break;
      case 'event': break;
      case 'assignment': onAssignment(msg.payload); break;
      case 'error': toast('SERVER: ' + ((msg.payload && msg.payload.message) || 'error'), 'danger'); break;
      default: break;
    }
  }

  function onState(state) {
    if (!state || !state.building) return;
    var prevStatus = app.me && app.me.status;
    app.state = state;
    render();
    if (app.me && prevStatus && prevStatus !== app.me.status) {
      toast('STATUS: ' + (STATUS_LABEL[app.me.status] || app.me.status), app.me.status === 'OK' ? 'ok' : 'danger');
    }
    resolvePending();
  }

  /** A delta names ids that only exist in the *next* state snapshot: remember them. */
  function onDelta(delta) {
    if (!delta) return;
    (delta.changed_victims || []).forEach(function (id) { if (app.pendingVictims.indexOf(id) < 0) app.pendingVictims.push(id); });
    (delta.changed_hazards || []).forEach(function (id) { if (app.pendingHazards.indexOf(id) < 0) app.pendingHazards.push(id); });
    if (delta.touch && delta.touch.responder_id === app.id) {
      toast('COMMAND RECEIVED: ' + String(delta.touch.action).replace('_', ' ').toUpperCase(), 'ok', 2500);
    }
    if (app.state) resolvePending();
  }

  function resolvePending() {
    if (!app.state) return;
    var floor = app.floor;
    var victims = app.state.victims || {};
    var hazards = app.state.hazards || {};
    app.pendingVictims = app.pendingVictims.filter(function (id) {
      var v = victims[id];
      if (!v) return true; // not in this snapshot yet
      if (v.cell && v.cell.floor === floor) {
        var where = v.zone || ('cell ' + v.cell.x + ',' + v.cell.y);
        var what = v.status === 'extracted' ? 'VICTIM OUT' : (v.status === 'confirmed' ? 'VICTIM CONFIRMED' : 'POSSIBLE VICTIM');
        toast(what + ' · ' + where.toUpperCase() + ' · ' + Math.round((v.probability || 0) * 100) + '%', v.status === 'extracted' ? 'ok' : 'victim', 4500);
      }
      return false;
    });
    app.pendingHazards = app.pendingHazards.filter(function (id) {
      var h = hazards[id];
      if (!h) return true;
      if (h.active && h.cell && h.cell.floor === floor) {
        toast('HAZARD · ' + String(h.kind).toUpperCase() + ' · ' + (h.zone || '').toUpperCase(), 'danger', 4500);
      }
      return false;
    });
  }

  function onBriefing(b) {
    if (!b || b.responder_id !== app.id || !b.text) return;
    if (app.briefings.some(function (x) { return x.id === b.id; })) return;
    app.briefings.unshift(b);
    if (app.briefings.length > 50) app.briefings.pop();
    app.unread.push(b.id);
    showBriefing(b);
    if (b.show_cell) app.showCell = b.show_cell;
    var card = $('briefing');
    card.classList.remove('flash');
    void card.offsetWidth;
    card.classList.add('flash');
    // Browsers refuse vibrate() before the first user gesture (and log an error); only try after one.
    if (navigator.vibrate && userTapped) { try { navigator.vibrate(b.urgency === 'critical' ? [200, 80, 200] : 120); } catch (e) { /* ignore */ } }
    if (app.audioEnabled && !app.muted) markRead(b.id);
    speech.say(b.urgency === 'critical' ? 'Urgent. ' + b.text : b.text);
    renderMap();
  }

  function showBriefing(b) {
    app.current = b;
    renderBriefing();
  }

  function markRead(id) {
    app.unread = app.unread.filter(function (x) { return x !== id; });
    renderBriefing();
  }

  function nextUnread() {
    if (!app.unread.length) return;
    var id = app.unread[0];
    var b = app.briefings.filter(function (x) { return x.id === id; })[0];
    markRead(id);
    if (!b) return;
    showBriefing(b);
    if (b.show_cell) { app.showCell = b.show_cell; renderMap(); }
    speech.say(b.text);
  }

  function onTranscript(t) {
    if (!t || !t.final || !t.text) return;
    if (t.responder_id && t.responder_id !== app.id) return;
    toast('RADIO: ' + t.text, 'status', 4000);
  }

  function onAssignment(a) {
    if (!a || a.responder_id !== app.id || a.accepted !== true) return;
    toast('ASSIGNED: ' + a.target_kind.toUpperCase() + ' ' + a.target_id, 'victim', 4500);
  }

  // ------------------------------------------------------------ network
  function wsUrl() {
    var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    return proto + location.host + '/ws';
  }

  function setConn(mode, text) {
    var c = $('conn');
    c.className = 'conn mono ' + mode;
    $('connText').textContent = text;
  }

  function connect() {
    if (MOCK) return;
    var ws;
    try { ws = new WebSocket(wsUrl()); } catch (e) { scheduleReconnect(); return; }
    app.ws = ws;
    setConn('reconnecting', 'CONNECTING');
    ws.onopen = function () {
      app.connected = true;
      app.backoff = 1000;
      setConn('live', 'LIVE');
      fetchState(); // belt and braces: the server also pushes 'state' on connect
    };
    ws.onmessage = function (ev) {
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      handleMessage(msg);
    };
    ws.onerror = function () { /* onclose follows */ };
    ws.onclose = function () {
      app.connected = false;
      app.ws = null;
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    setConn('reconnecting', 'RECONNECTING');
    var wait = app.backoff;
    app.backoff = Math.min(app.backoff * 2, 8000);
    setTimeout(connect, wait);
  }

  function fetchState() {
    if (MOCK) return;
    fetch('/api/state', { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (state) { onState(state); })
      .catch(function () { /* the WS snapshot will arrive */ });
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  // -------------------------------------------------------------- touch
  var ACTION_LABEL = { mark_victim: 'VICTIM MARKED', need_help: 'HELP REQUESTED', victim_out: 'VICTIM OUT', im_ok: "I'M OK" };

  function sendTouch(action, cell, btn) {
    var payload = { responder_id: app.id, action: action, cell: cell || null };
    if (btn) { btn.classList.remove('sent'); void btn.offsetWidth; btn.classList.add('sent'); }
    if (MOCK) {
      mock.applyTouch(payload);
      toast('SENT: ' + ACTION_LABEL[action], 'ok', 2000);
      return Promise.resolve();
    }
    return postJson('/api/touch', payload)
      .then(function () { toast('SENT: ' + ACTION_LABEL[action], 'ok', 2000); })
      .catch(function () { toast('SEND FAILED · ' + ACTION_LABEL[action], 'danger'); });
  }

  function enterMarkMode() {
    app.markMode = true;
    app.markCell = app.me && app.me.cell ? { floor: app.me.cell.floor, x: app.me.cell.x, y: app.me.cell.y } : null;
    renderMap();
    renderButtons();
  }

  function exitMarkMode() {
    app.markMode = false;
    app.markCell = null;
    renderMap();
    renderButtons();
  }

  // -------------------------------------------------------------- photo
  function blobToImage(blob) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(blob);
      var img = new Image();
      img.onload = function () { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('bad image')); };
      img.src = url;
    });
  }

  /** Downscale to max PHOTO_MAX px and return {dataUrl, b64, width, height}. */
  function downscale(img) {
    var scale = Math.min(1, PHOTO_MAX / Math.max(img.naturalWidth || img.width, img.naturalHeight || img.height));
    var w = Math.max(1, Math.round((img.naturalWidth || img.width) * scale));
    var h = Math.max(1, Math.round((img.naturalHeight || img.height) * scale));
    var c = document.createElement('canvas');
    c.width = w; c.height = h;
    c.getContext('2d').drawImage(img, 0, 0, w, h);
    var dataUrl = c.toDataURL('image/jpeg', 0.85);
    return { dataUrl: dataUrl, b64: dataUrl.split(',')[1], width: w, height: h };
  }

  /** Base64 of the blob's original bytes (no data: prefix). */
  function blobToB64(blob) {
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onload = function () { resolve(String(fr.result).split(',')[1] || ''); };
      fr.onerror = function () { reject(new Error('read failed')); };
      fr.readAsDataURL(blob);
    });
  }

  function sendPhoto(blob, sampleName) {
    $('photoCaption').textContent = 'ANALYSING…';
    $('photoCaption').className = 'photo-caption mono';
    $('photoOverlay').hidden = false;
    return blobToImage(blob).then(function (img) {
      var pic = downscale(img);
      drawPhoto(pic.dataUrl, [], true);
      // A JPEG that already fits is sent byte-for-byte: re-encoding through a canvas
      // strips JPEG metadata (the sample frames' marker) and costs quality for nothing.
      var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
      var asIs = blob.type === 'image/jpeg' && Math.max(w, h) <= PHOTO_MAX;
      var b64p = asIs ? blobToB64(blob).catch(function () { return pic.b64; }) : Promise.resolve(pic.b64);
      var req = MOCK
        ? mock.detect(sampleName)
        : b64p.then(function (b64) {
          return postJson('/api/photo', { responder_id: app.id, image_b64: b64 || pic.b64, mime: 'image/jpeg' });
        });
      return req.then(function (res) {
        var dets = normalizeDetections(res && res.detections);
        drawPhoto(pic.dataUrl, dets, false);
      });
    }).catch(function (err) {
      $('photoCaption').textContent = 'PHOTO FAILED';
      $('photoCaption').className = 'photo-caption mono error';
      schedulePhotoHide();
      console.warn('photo failed', err);
    });
  }

  function normalizeDetections(list) {
    if (!Array.isArray(list)) return [];
    return list.filter(function (d) {
      return d && isFinite(d.x0) && isFinite(d.y0) && isFinite(d.x1) && isFinite(d.y1);
    }).map(function (d) {
      return { label: d.label || 'person', score: +d.score || 0, x0: +d.x0, y0: +d.y0, x1: +d.x1, y1: +d.y1 };
    });
  }

  var photoHideTimer = null;
  function schedulePhotoHide() {
    clearTimeout(photoHideTimer);
    photoHideTimer = setTimeout(function () { $('photoOverlay').hidden = true; }, PHOTO_SHOW_MS);
  }

  function drawPhoto(dataUrl, dets, pending) {
    var canvas = $('photoCanvas');
    var img = new Image();
    img.onload = function () {
      var maxW = 320, maxH = 180;
      var s = Math.min(maxW / img.width, maxH / img.height, 1);
      canvas.width = Math.round(img.width * s);
      canvas.height = Math.round(img.height * s);
      var ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 3;
      ctx.strokeStyle = '#ffb020';
      ctx.fillStyle = '#ffb020';
      ctx.font = 'bold 12px monospace';
      dets.forEach(function (d) {
        var x = d.x0 * canvas.width, y = d.y0 * canvas.height;
        var w = (d.x1 - d.x0) * canvas.width, h = (d.y1 - d.y0) * canvas.height;
        ctx.strokeRect(x, y, w, h);
        ctx.fillText(Math.round(d.score * 100) + '%', x + 3, Math.max(12, y - 4));
      });
      if (!pending) {
        var n = dets.length;
        var cap = $('photoCaption');
        cap.textContent = n + (n === 1 ? ' PERSON DETECTED' : ' PEOPLE DETECTED');
        cap.className = 'photo-caption mono' + (n === 0 ? ' none' : '');
        if (n > 0) speech.say(n + (n === 1 ? ' person' : ' people') + ' detected on camera.');
        schedulePhotoHide();
      }
    };
    img.src = dataUrl;
  }

  function onCamPick(evt) {
    var file = evt.target.files && evt.target.files[0];
    evt.target.value = '';
    if (!file) return;
    sendPhoto(file, null);
  }

  function onSamplePick(name) {
    if (MOCK) {
      mock.sampleBlob(name).then(function (blob) { sendPhoto(blob, name); });
      return;
    }
    fetch('/samples/' + name + '.jpg')
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.blob(); })
      .then(function (blob) { sendPhoto(blob, name); })
      .catch(function () { toast('SAMPLE NOT AVAILABLE', 'danger'); });
  }

  function loadSampleThumbs() {
    var buttons = document.querySelectorAll('.sample');
    Array.prototype.forEach.call(buttons, function (btn) {
      var name = btn.getAttribute('data-sample');
      var img = btn.querySelector('img');
      if (MOCK) {
        var c = mock.sampleCanvas(name, 48, 60);
        btn.replaceChild(c, img);
      } else {
        img.src = '/samples/' + name + '.jpg';
        img.onerror = function () { img.removeAttribute('src'); btn.textContent = name.split('_')[0].slice(0, 5).toUpperCase(); };
      }
    });
  }

  // ---------------------------------------------------------------- wiring
  function bind() {
    $('btnMark').addEventListener('click', enterMarkMode);
    $('btnHelp').addEventListener('click', function () { sendTouch('need_help', app.me && app.me.cell, this); });
    $('btnOut').addEventListener('click', function () { sendTouch('victim_out', app.me && app.me.cell, this); });
    $('btnOk').addEventListener('click', function () { sendTouch('im_ok', app.me && app.me.cell, this); });
    $('btnConfirm').addEventListener('click', function () {
      if (!app.markCell) return;
      var cell = app.markCell;
      sendTouch('mark_victim', cell, this);
      exitMarkMode();
    });
    $('btnCancel').addEventListener('click', exitMarkMode);
    $('map').addEventListener('click', onMapTap);

    $('unreadBtn').addEventListener('click', nextUnread);
    $('muteBtn').addEventListener('click', function () {
      app.muted = !app.muted;
      savePref('fireline.muted', app.muted);
      if (app.muted) speech.stop();
      renderBriefing();
    });

    $('camBtn').addEventListener('click', function () { $('camInput').click(); });
    $('camInput').addEventListener('change', onCamPick);
    Array.prototype.forEach.call(document.querySelectorAll('.sample'), function (btn) {
      btn.addEventListener('click', function () { onSamplePick(btn.getAttribute('data-sample')); });
    });

    $('audioBtn').addEventListener('click', function () {
      speech.enable();
      $('audioOverlay').hidden = true;
      if (app.current && !app.muted) { markRead(app.current.id); speech.say(app.current.text); }
    });
    $('audioSkip').addEventListener('click', function () { $('audioOverlay').hidden = true; });

    setInterval(function () { if (app.current) $('briefingAgo').textContent = ago(app.current.timestamp); }, 5000);
  }

  function start() {
    bind();
    loadSampleThumbs();
    renderBriefing();
    if (MOCK) {
      setConn('mock', 'MOCK');
      mock.start();
    } else {
      fetchState();
      connect();
    }
  }

  // =====================================================================
  // Mock harness (?mock=1): hard-coded slice of data/scenario.json + timeline
  // =====================================================================
  var mock = (function () {
    var Z = function (name, floor, x0, y0, x1, y1, kind) {
      return { name: name, floor: floor, x0: x0, y0: y0, x1: x1, y1: y1, kind: kind || 'room', aliases: [] };
    };
    var zones = [
      Z('command post', 0, 2, 2, 8, 6, 'outdoor'), Z('staging area', 0, 10, 2, 24, 8, 'outdoor'),
      Z('north entrance', 0, 26, 9, 33, 12, 'outdoor'), Z('parking lot', 0, 44, 2, 58, 30, 'outdoor'),
      Z('hydrant', 0, 12, 32, 13, 33, 'outdoor'), Z('south alley', 0, 18, 29, 41, 33, 'outdoor'),
      Z('engine 1 position', 0, 20, 8, 25, 11, 'outdoor'), Z('ladder 2 position', 0, 34, 8, 41, 11, 'outdoor'),

      Z('lobby', 1, 9, 0, 14, 4, 'lobby'), Z('elevator lobby 1', 1, 10, 5, 13, 8, 'lobby'),
      Z('stairwell A', 1, 21, 5, 23, 8, 'stair'), Z('stairwell B', 1, 0, 5, 2, 8, 'stair'),
      Z('east corridor 1', 1, 14, 6, 20, 7, 'corridor'), Z('west corridor 1', 1, 3, 6, 9, 7, 'corridor'),
      Z('cafe', 1, 15, 9, 23, 13), Z('convenience store', 1, 0, 9, 8, 13), Z('pharmacy', 1, 0, 0, 8, 4), Z('bank', 1, 15, 0, 23, 4)
    ];
    // floors 2-5 share the same core; rooms differ
    var rooms = {
      2: [['gym', 3, 0, 20, 4], ['restaurant', 3, 9, 20, 13], ['restaurant office', 21, 9, 23, 13], ['storage 2', 0, 9, 2, 13]],
      3: [['unit 301', 0, 0, 8, 4], ['unit 302', 15, 0, 23, 4], ['unit 303', 0, 9, 8, 13], ['unit 304', 15, 9, 23, 13]],
      4: [['unit 401', 0, 0, 8, 4], ['unit 402', 15, 0, 23, 4], ['unit 403', 0, 9, 8, 13], ['unit 404', 15, 9, 23, 13]],
      5: [['unit 501', 0, 0, 8, 4], ['unit 502', 15, 0, 23, 4], ['unit 503', 0, 9, 8, 13], ['unit 504', 15, 9, 23, 13]]
    };
    for (var f = 2; f <= 5; f++) {
      zones.push(Z('elevator lobby ' + f, f, 10, 5, 13, 8, 'lobby'));
      zones.push(Z('stairwell A', f, 21, 5, 23, 8, 'stair'));
      zones.push(Z('stairwell B', f, 0, 5, 2, 8, 'stair'));
      zones.push(Z('east corridor ' + f, f, 14, 6, 20, 7, 'corridor'));
      zones.push(Z('west corridor ' + f, f, 3, 6, 9, 7, 'corridor'));
      rooms[f].forEach(function (r) { zones.push(Z(r[0], f, r[1], r[2], r[3], r[4])); });
    }

    var building = {
      name: 'Hanul Tower', address: '27 Seongsu-ro (fictional)', floors: 5, width: 24, height: 14,
      geo_origin: { lat: 37.5448, lon: 127.0557 }, meters_per_cell: 1.5, bearing_deg: 0,
      site_width: 60, site_height: 40, footprint_x: 18, footprint_y: 13, zones: zones
    };

    var R = function (id, name, unit, role, cell, zone) {
      return { id: id, name: name, unit: unit, role: role, status: 'OK', cell: cell, zone: zone, air_minutes: 30,
        last_report_id: null, last_seen: new Date().toISOString(), track: [] };
    };
    var state = {
      version: 0,
      incident_name: 'Structure fire — Hanul Tower',
      building: building,
      responders: {
        'E1-1': R('E1-1', 'Capt. Kim Dohyun', 'Engine 1', 'attack team lead', { floor: 0, x: 22, y: 9 }, 'engine 1 position'),
        'E1-2': R('E1-2', 'FF Park Jiwoo', 'Engine 1', 'nozzle', { floor: 0, x: 23, y: 10 }, 'engine 1 position'),
        'L2-1': R('L2-1', 'Lt. Lee Seojin', 'Ladder 2', 'search & rescue lead', { floor: 0, x: 36, y: 9 }, 'ladder 2 position'),
        'R3-1': R('R3-1', 'FF Choi Minjae', 'Rescue 3', 'rescue', { floor: 0, x: 12, y: 4 }, 'staging area'),
        'R3-2': R('R3-2', 'FF Han Yuna', 'Rescue 3', 'rescue', { floor: 0, x: 13, y: 5 }, 'staging area')
      },
      victims: {}, hazards: {}, queue: [], events: [], updated_at: new Date().toISOString()
    };
    var seq = 0;
    var nid = function (p) { return p + '_mock' + (++seq); };
    var now = function () { return new Date().toISOString(); };

    function emit(type, payload) { handleMessage({ type: type, payload: JSON.parse(JSON.stringify(payload)) }); }

    function delta(changes) {
      state.version += 1;
      state.updated_at = now();
      var d = { version: state.version, triage: null, touch: changes.touch || null, detections: [],
        changed_responders: changes.responders || [], changed_victims: changes.victims || [],
        changed_hazards: changes.hazards || [], new_events: [], timestamp: now() };
      emit('delta', d);
      emit('state', state);
    }

    function moveMe(id, cell, zone, status) {
      var r = state.responders[id];
      r.cell = cell; r.zone = zone; r.last_seen = now();
      if (status) r.status = status;
      r.track.push(cell);
      delta({ responders: [id] });
    }

    function addVictim(cell, zone, p, status, count, source) {
      var id = nid('vic');
      state.victims[id] = { id: id, cell: cell, zone: zone, probability: p, status: status, count: count || 1,
        condition: null, source_report_ids: [], source: source || 'radio', assigned_responder_id: null,
        created_at: now(), updated_at: now() };
      delta({ victims: [id] });
      return id;
    }

    function addHazard(kind, cell, zone, sev) {
      var id = nid('haz');
      state.hazards[id] = { id: id, kind: kind, cell: cell, zone: zone, severity: sev || 3, source_report_ids: [], active: true, created_at: now() };
      delta({ hazards: [id] });
      return id;
    }

    function brief(text, urgency, showCell) {
      emit('briefing', { id: nid('brf'), responder_id: app.id, text: text, urgency: urgency || 'normal', reason: 'mock',
        trigger_ids: [], show_cell: showCell || null, timestamp: now() });
    }

    function myId() { return state.responders[app.id] ? app.id : 'L2-1'; }

    var timeline = [
      [1500, function () { brief('Ladder 2, Engine 1 is on stairwell A. Smoke banking down to two. Use stairwell B.', 'normal'); }],
      [4500, function () { moveMe(myId(), { floor: 4, x: 6, y: 6 }, 'west corridor 4'); }],
      [7000, function () { addVictim({ floor: 4, x: 19, y: 11 }, 'unit 404', 0.6, 'suspected', 1); }],
      [7600, function () { brief('Possible victim in unit 404, door jammed. Irons coming up stairwell B.', 'high', { floor: 4, x: 19, y: 11 }); }],
      [12000, function () { addHazard('heavy smoke', { floor: 4, x: 17, y: 6 }, 'east corridor 4', 3); }],
      [15000, function () { state.responders['R3-2'].status = 'InDanger'; state.responders['R3-2'].cell = { floor: 5, x: 1, y: 6 }; state.responders['R3-2'].zone = 'stairwell B'; delta({ responders: ['R3-2'] }); }],
      [15500, function () { brief('Mayday fifth floor stairwell B, ceiling collapse. Do not use stairwell B. Egress via stairwell A.', 'critical', null); }],
      [19000, function () { addHazard('collapse above', { floor: 4, x: 1, y: 6 }, 'stairwell B', 5); }],
      [23000, function () { addVictim({ floor: 4, x: 4, y: 11 }, 'unit 403', 0.45, 'suspected', 1, 'camera'); }],
      [27000, function () { brief('Command copies. Continue search of four. RIT is on the way to five.', 'low'); }],
      [32000, function () { moveMe('E1-1', { floor: 4, x: 22, y: 6 }, 'stairwell A'); }],
      [36000, function () { brief('Engine 1 joining you on four via stairwell A.', 'normal', { floor: 4, x: 22, y: 6 }); }]
    ];

    function start() {
      emit('state', state);
      timeline.forEach(function (step) { setTimeout(step[1], step[0]); });
      setInterval(function () {
        var me = state.responders[myId()];
        if (me.air_minutes > 0) me.air_minutes -= 1;
        delta({ responders: [me.id] });
      }, 10000);
    }

    /** Apply a TouchInput locally using the worldmodel rules from the contract. */
    function applyTouch(t) {
      var me = state.responders[t.responder_id];
      if (!me) return;
      if (t.action === 'mark_victim' && t.cell) {
        var z = (function () { for (var i = 0; i < zones.length; i++) { var zz = zones[i]; if (zz.floor === t.cell.floor && zz.x0 <= t.cell.x && t.cell.x <= zz.x1 && zz.y0 <= t.cell.y && t.cell.y <= zz.y1) return zz.name; } return null; })();
        var id = nid('vic');
        state.victims[id] = { id: id, cell: t.cell, zone: z, probability: 0.9, status: 'confirmed', count: 1, condition: null,
          source_report_ids: [], source: 'touch', assigned_responder_id: null, created_at: now(), updated_at: now() };
        delta({ victims: [id], responders: [], touch: t });
      } else if (t.action === 'need_help') {
        me.status = 'NeedsHelp'; delta({ responders: [me.id], touch: t });
        setTimeout(function () { brief('Help request received. Nearest crew Engine 1 is coming to you.', 'high'); }, 1200);
      } else if (t.action === 'im_ok' || t.action === 'clear_danger') {
        me.status = 'OK'; delta({ responders: [me.id], touch: t });
      } else if (t.action === 'victim_out') {
        var best = null, bd = 1e9;
        values(state.victims).forEach(function (v) {
          if (v.status === 'extracted' || !me.cell || v.cell.floor !== me.cell.floor) return;
          var d = cellDist(me.cell, v.cell); if (d < bd) { bd = d; best = v; }
        });
        if (best) { best.status = 'extracted'; best.updated_at = now(); delta({ victims: [best.id], touch: t }); }
        else delta({ touch: t });
      }
    }

    /** Fake SAM result for a sample name (filename contains "victim" -> detections). */
    function detect(name) {
      var dets = [];
      if (name === 'smoky_room_victim') dets = [{ label: 'person', score: 0.87, x0: 0.55, y0: 0.45, x1: 0.78, y1: 0.92 }];
      if (name === 'two_victims_404') dets = [
        { label: 'person', score: 0.91, x0: 0.18, y0: 0.4, x1: 0.4, y1: 0.95 },
        { label: 'person', score: 0.74, x0: 0.6, y0: 0.5, x1: 0.76, y1: 0.9 }];
      if (name === null) dets = [{ label: 'person', score: 0.66, x0: 0.3, y0: 0.3, x1: 0.6, y1: 0.9 }];
      return new Promise(function (resolve) {
        setTimeout(function () {
          if (dets.length) {
            var me = state.responders[myId()];
            addVictim(me.cell, me.zone, 0.5 + 0.4 * dets[0].score, 'suspected', dets.length, 'camera');
          }
          resolve({ detections: dets, delta: null, latency_ms: 420 });
        }, 700);
      });
    }

    /** Pillow-style synthetic frame: smoky gradient with 0-2 silhouettes. */
    function sampleCanvas(name, w, h) {
      var c = document.createElement('canvas');
      c.width = w; c.height = h;
      var ctx = c.getContext('2d');
      var grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, name === 'corridor_clear' ? '#3a4452' : '#2b2622');
      grad.addColorStop(1, name === 'corridor_clear' ? '#1a2029' : '#0e0c0a');
      ctx.fillStyle = grad; ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = 'rgba(255,140,40,0.25)';
      if (name !== 'corridor_clear') ctx.fillRect(0, 0, w, h * 0.35);
      ctx.fillStyle = '#c8c0b4';
      var figs = name === 'two_victims_404' ? [[0.25, 0.4], [0.65, 0.5]] : name === 'smoky_room_victim' ? [[0.6, 0.45]] : [];
      figs.forEach(function (f) {
        var x = f[0] * w, y = f[1] * h;
        ctx.beginPath(); ctx.arc(x, y, w * 0.08, 0, Math.PI * 2); ctx.fill();
        ctx.fillRect(x - w * 0.09, y + w * 0.08, w * 0.18, h * 0.4);
      });
      if (name === 'corridor_clear') { ctx.strokeStyle = '#55657a'; ctx.lineWidth = 2; ctx.strokeRect(w * 0.2, h * 0.1, w * 0.6, h * 0.8); }
      return c;
    }

    function sampleBlob(name) {
      return new Promise(function (resolve) {
        var c = sampleCanvas(name, 640, 480);
        if (c.toBlob) c.toBlob(function (b) { resolve(b); }, 'image/jpeg', 0.9);
        else {
          var bin = atob(c.toDataURL('image/jpeg', 0.9).split(',')[1]);
          var arr = new Uint8Array(bin.length);
          for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
          resolve(new Blob([arr], { type: 'image/jpeg' }));
        }
      });
    }

    return { start: start, applyTouch: applyTouch, detect: detect, sampleCanvas: sampleCanvas, sampleBlob: sampleBlob };
  })();

  // expose a little for debugging in the console
  window.fireline = { app: app, handleMessage: handleMessage, mock: MOCK };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();

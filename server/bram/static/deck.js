"use strict";
// BRAM's Home: a brain of light with the home's systems orbiting it. When something happens,
// a pulse runs from that system into the brain. Its voice ring follows what it says.
const deck = (() => {
  const $ = (id) => document.getElementById(id);
  const make = (tag, text, kind) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (kind) node.className = kind;
    return node;
  };
  const still = matchMedia("(prefers-reduced-motion: reduce)");
  const TAU = Math.PI * 2;
  let w = 0, h = 0, spin = 0, last = 0, speed = 1, frame = 0, mood = "ok", alarm = "", lastAlarm = 0;
  // When something happens, the brain takes that system's color for a few seconds.
  const HUES = { People: "#5dff9d", Lights: "#ffe066", Security: "#ffb84d", Safety: "#ff4d63", Climate: "#7ad7ff", Printers: "#b88cff", Messages: "#ff7ad9", Learning: "#b88cff", "Home Assistant": "#2fe6ff" };
  let tint = null;
  let level = 0;  // how loud the voice is now, smoothed
  const name = { born: 0, last: -1e9 };
  let readings = [], shown = { i: -1, born: 0, side: 1 };

  // A geodesic sphere: an icosahedron with each face split in four, on the unit sphere.
  const GEO = (() => {
    const p = (1 + Math.sqrt(5)) / 2;
    let points = [[-1, p, 0], [1, p, 0], [-1, -p, 0], [1, -p, 0], [0, -1, p], [0, 1, p], [0, -1, -p], [0, 1, -p], [p, 0, -1], [p, 0, 1], [-p, 0, -1], [-p, 0, 1]];
    let faces = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
    const unit = ([x, y, z]) => { const l = Math.hypot(x, y, z); return [x / l, y / l, z / l]; };
    points = points.map(unit);
    const middle = new Map(), mid = (a, b) => {
      const key = a < b ? `${a},${b}` : `${b},${a}`;
      if (!middle.has(key)) { points.push(unit(points[a].map((v, k) => (v + points[b][k]) / 2))); middle.set(key, points.length - 1); }
      return middle.get(key);
    };
    faces = faces.flatMap(([a, b, c]) => { const ab = mid(a, b), bc = mid(b, c), ca = mid(c, a); return [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]; });
    const edges = new Set();
    for (const [a, b, c] of faces) for (const [x, y] of [[a, b], [b, c], [c, a]]) edges.add(x < y ? `${x},${y}` : `${y},${x}`);
    return { points, edges: [...edges].map((e) => e.split(",").map(Number)) };
  })();

  // The dots that spell BRAM, read once from the letters drawn off screen.
  const NAME = (() => {
    const c = document.createElement("canvas"), width = 360, height = 110;
    c.width = width; c.height = height;
    const g = c.getContext("2d");
    g.fillStyle = "#fff"; g.font = "800 96px ui-monospace, Consolas, monospace"; g.textBaseline = "middle"; g.textAlign = "center";
    g.fillText("BRAM", width / 2, height / 2);
    const pixels = g.getImageData(0, 0, width, height).data, dots = [];
    for (let y = 0; y < height; y += 3) for (let x = 0; x < width; x += 3) {
      if (pixels[(y * width + x) * 4 + 3] > 128) dots.push({ x, y, fx: Math.random(), fy: Math.random(), dx: Math.random() - .5, dy: Math.random() - .5, ph: Math.random() * 6 });
    }
    return { dots, width, height };
  })();

  function spell() {
    const now = performance.now();
    if (now - name.last > 8000) { name.born = now; name.last = now; wake(); }
  }

  // Readings to point out, such as [{label: "Living room", value: "74°"}].
  function points(list) { readings = list.slice(0, 12); }

  function callout(g, o, r, now) {
    if (!readings.length) return;
    if (!shown.born || now - shown.born > 7000) {
      shown = { i: (shown.i + 1) % readings.length, born: now, side: -shown.side };
    }
    const item = readings[shown.i], age = (now - shown.born) / 1000;
    if (!item) return;
    const fade = Math.min(1, age / .3) * Math.max(0, Math.min(1, (6.4 - age) / .6));
    const a = shown.side > 0 ? -.55 : Math.PI + .55, start = r * 1.25;
    const x0 = o.x + Math.cos(a) * start, y0 = o.y + Math.sin(a) * start;
    const x1 = o.x + Math.cos(a) * r * 2.35, y1 = o.y + Math.sin(a) * r * 2.35;
    const x2 = x1 + shown.side * 110;
    const grow = Math.min(1, age / .7);  // the line draws itself, then the label appears
    g.globalAlpha = .8 * fade; g.strokeStyle = color.main; g.lineWidth = 1;
    g.beginPath(); g.moveTo(x0, y0);
    const first = Math.min(1, grow * 2), second = Math.max(0, grow * 2 - 1);
    g.lineTo(x0 + (x1 - x0) * first, y0 + (y1 - y0) * first);
    if (second) g.lineTo(x1 + (x2 - x1) * second, y1);
    g.stroke();
    g.fillStyle = color.main; g.fillRect(x0 - 2, y0 - 2, 4, 4);
    if (grow < 1) { g.globalAlpha = 1; return; }
    const label = item.label.toUpperCase(), value = item.value;
    g.font = "600 12px ui-monospace, Consolas, monospace";
    const width = Math.max(150, g.measureText(label).width + g.measureText(value).width + 44);
    const bx = shown.side > 0 ? x2 : x2 - width, by = y1 - 14, show = Math.min(1, (age - .7) / .35) * fade;
    g.globalAlpha = .85 * show; g.fillStyle = "rgba(0,10,22,.85)"; g.fillRect(bx, by, width, 28);
    g.strokeStyle = color.main; g.strokeRect(bx + .5, by + .5, width - 1, 27);
    g.fillStyle = color.text; g.textAlign = "left"; g.textBaseline = "middle"; g.fillText(label, bx + 10, by + 14);
    g.fillStyle = color.main; g.textAlign = "right"; g.fillText(value, bx + width - 10, by + 14);
    g.globalAlpha = 1; g.textBaseline = "alphabetic";
  }
  let color = {}, dust = [], threads = [], systems = [], pulses = [], waves = [], flashes = {};
  let placed = [];
  let ear = null, earKind = "", heard = null, talking = 0, voice = [], sayTimer = 0, outdoor = null;

  function colors() {
    const style = getComputedStyle(document.body);
    const read = (name) => style.getPropertyValue(name).trim();
    color = { main: read("--hud") || "#2fe6ff", dim: read("--hud-dim"), warn: read("--hud-warn"), bad: read("--hud-bad"), text: read("--hud-text"), sky: "#7ad7ff", violet: "#b88cff", pink: "#ff7ad9" };
    const hues = [color.main, color.main, color.sky, color.violet, color.pink, "#ffffff"];
    threads = Array.from({ length: 150 }, () => ({ a: Math.random() * TAU, len: .55 + Math.random() * .9, bend: (Math.random() - .5) * 1.4, ph: Math.random() * 6, sp: .2 + Math.random() * .6, color: hues[Math.floor(Math.random() * hues.length)], width: .4 + Math.random() * 1.3 }));
  }

  // --- what the page tells the brain ---

  function update(groups) {
    const all = groups.flatMap((group) => group.devices);
    mood = all.some((d) => d.state === "alert") ? "bad" : all.some((d) => d.state === "warn") ? "warn" : "ok";
  }

  // Something is wrong: "bad" sends red rings out often, "warn" amber ones now and then.
  function alert(level) {
    alarm = level === "bad" || level === "warn" ? level : "";
    wake();
  }

  // The systems on the orbit: [{name, value, hot: "" | "warn" | "bad"}]
  function orbit(list) { systems = list; }

  // Something happened in one system: it flashes and a pulse runs into the brain.
  function pulse(name, kind = "main") {
    const i = systems.findIndex((s) => s.name === name), now = performance.now();
    flashes[name] = now;
    const hue = kind === "bad" || kind === "warn" ? color[kind] : HUES[name] || color[kind] || color.main;
    if (i >= 0) pulses.push({ i, born: now, color: hue });
    else waves.push({ born: now, color: hue });
    tint = { color: hue, born: now, hold: kind === "bad" ? 6000 : 3500 };
    wake();
  }

  function state(which) {
    for (const s of ["watch", "listen", "think", "speak"]) $(`s-${s}`)?.classList.toggle("on", s === which);
  }

  // BRAM's words appear as it says them. With real audio playing, the ring follows the sound.
  function say(text) {
    clearInterval(sayTimer);
    const out = $("thought-text");
    if (!out) return;
    let i = 0;
    out.textContent = "";
    talking = 1;
    state("speak");
    sayTimer = setInterval(() => {
      const ch = text[i] || " ";
      out.textContent = text.slice(0, i + 1);
      if (!ear) {
        const loud = /[aeiouAEIOU]/.test(ch) ? 1 : /[ ,.]/.test(ch) ? .12 : .6;
        voice = Array.from({ length: 72 }, (_, k) => loud * (.3 + .7 * Math.abs(Math.sin(k * 1.3 + i * .7))) * (.6 + Math.random() * .4));
      }
      i += Math.max(1, Math.ceil(text.length / 140));
      if (i >= text.length) {
        out.textContent = text;
        clearInterval(sayTimer);
        setTimeout(() => { if (!ear) { talking = 0; state(speed > 1 ? "think" : "watch"); } }, 400);
      }
    }, 40);
    wake();
  }

  function think(on) {
    speed = on ? 4 : 1;
    if (on) state("think");
    else if (!talking) state("watch");
  }

  // A real voice to follow: BRAM speaking, or you talking to it.
  function listen(node, kind = "") {
    ear = node;
    earKind = node ? kind : "";
    heard = null;
    if (node) { talking = 1; state(kind === "listening" ? "listen" : "speak"); if (kind !== "listening") spell(); }
    else { talking = 0; state(speed > 1 ? "think" : "watch"); }
    wake();
  }

  function weather(degrees) { outdoor = degrees; }

  // --- the house, drawn from its rooms ---

  function house(rooms) {
    const plan = $("plan");
    if (!plan) return;
    const shown = rooms.slice(0, 16), cols = Math.max(1, Math.ceil(Math.sqrt(shown.length * 1.5)));
    const cw = 230 / cols, ch = 150 / Math.max(1, Math.ceil(shown.length / cols));
    plan.replaceChildren(...shown.flatMap((room, i) => {
      const box = make("div", room.name.slice(0, 12).toUpperCase(), `room${room.lit ? " lit" : ""}${room.open ? " warn" : ""}`);
      const x = (i % cols) * cw, y = Math.floor(i / cols) * ch;
      Object.assign(box.style, { left: `${x}px`, top: `${y}px`, width: `${cw}px`, height: `${ch}px` });
      box.title = room.name;
      const people = room.people.map((name, k) => {
        const dot = make("i", undefined, "person");
        dot.title = name;
        Object.assign(dot.style, { left: `${x + cw / 2 + (k - (room.people.length - 1) / 2) * 12}px`, top: `${y + ch * .72}px` });
        return dot;
      });
      return [box, ...people];
    }));
  }

  // --- drawing ---

  const canvas = () => $("scope");
  function size() {
    const node = canvas(), box = node.getBoundingClientRect(), ratio = Math.min(devicePixelRatio || 1, 2);
    if (!box.width) return false;
    if (w !== box.width || h !== box.height) {
      w = box.width; h = box.height;
      node.width = Math.round(w * ratio); node.height = Math.round(h * ratio);
      dust = Array.from({ length: 140 }, () => ({ x: Math.random() * w, y: Math.random() * h, z: Math.random(), v: .05 + Math.random() * .25 }));
    }
    node.getContext("2d").setTransform(ratio, 0, 0, ratio, 0, 0);
    return true;
  }

  function ellipse(g, cx, cy, rx, ry, from, to, width, stroke, alpha, dash) {
    g.save(); g.globalAlpha = alpha; g.strokeStyle = stroke; g.lineWidth = width; g.setLineDash(dash || []);
    g.beginPath(); g.ellipse(cx, cy, rx, ry, 0, from, to); g.stroke(); g.restore();
  }

  function center() { return { x: w / 2, y: h * .45, r: Math.min(w * .1, h * .13) }; }

  // The orbit stays in the open space between the side screens.
  function orbitWidth(o) {
    const left = $("hud-left"), side = left?.getBoundingClientRect(), box = canvas().getBoundingClientRect();
    const beside = side && side.width && getComputedStyle(left).position === "absolute";
    const room = beside ? o.x - (side.right - box.left) - 150 : w * .38;
    return Math.max(o.r * 1.6, Math.min(o.r * 3.1, room));
  }

  function place(i, t, o) {
    const a = (i / Math.max(systems.length, 1)) * TAU + t * .045, rx = orbitWidth(o);
    return { x: o.x + Math.cos(a) * rx, y: o.y + Math.sin(a) * o.r * 1.5, depth: (Math.sin(a) + 1) / 2 };
  }

  function draw(time = 0) {
    if (!size()) return;
    const g = canvas().getContext("2d");
    const dt = last && time ? Math.min(time - last, 60) / 1000 : 0;
    if (time) last = time;
    if (!still.matches) spin += dt * (speed > 1 ? 1.8 : 1);
    const t = spin, o = center(), r = o.r, now = performance.now();
    const worst = alarm === "bad" || mood === "bad" ? "bad" : alarm === "warn" || mood === "warn" ? "warn" : "ok";
    const base = worst === "bad" ? color.bad : worst === "warn" ? color.warn : color.main;
    g.clearRect(0, 0, w, h);
    const glow = g.createRadialGradient(o.x, o.y, 0, o.x, o.y, Math.max(w, h) * .55);
    glow.addColorStop(0, "rgba(60,80,255,.18)"); glow.addColorStop(.4, "rgba(47,230,255,.05)"); glow.addColorStop(1, "rgba(1,5,16,0)");
    g.fillStyle = glow; g.fillRect(0, 0, w, h);
    for (const d of dust) {
      if (!still.matches) { d.y -= d.v; if (d.y < 0) { d.y = h; d.x = Math.random() * w; } }
      g.globalAlpha = .15 + d.z * .45; g.fillStyle = color.main; g.fillRect(d.x, d.y, 1 + d.z * 1.4, 1 + d.z * 1.4);
    }
    g.globalAlpha = 1;
    g.lineCap = "round";

    // the housing around the brain
    ellipse(g, o.x, o.y, orbitWidth(o), r * 1.5, 0, TAU, 1, color.main, .22, [3, 9]);
    g.save(); g.translate(o.x, o.y); g.rotate(t * .03);
    for (let i = 0; i < 240; i += 1) {
      const a = i / 240 * TAU, long = i % 20 === 0, R = r * 2.25;
      g.globalAlpha = long ? .7 : .22; g.strokeStyle = base; g.lineWidth = long ? 2 : 1;
      g.beginPath(); g.moveTo(Math.cos(a) * R, Math.sin(a) * R); g.lineTo(Math.cos(a) * (R + (long ? 14 : 7)), Math.sin(a) * (R + (long ? 14 : 7))); g.stroke();
    }
    g.restore();
    for (let s = 0; s < 4; s += 1) { const a0 = -t * .12 + s * TAU / 4; ellipse(g, o.x, o.y, r * 2.5, r * 2.5, a0, a0 + .9, 3, base, .55); }
    for (let s = 0; s < 3; s += 1) { const a0 = t * .2 + s * 2.1; ellipse(g, o.x, o.y, r * 1.95, r * 1.95, a0, a0 + 1.2, 6, base, .3); }

    const nodes = systems.map((s, i) => ({ s, i, ...place(i, t, o) })).sort((a, b) => a.depth - b.depth);
    const node = (n) => {
      const hot = n.s.hot === "bad" ? color.bad : n.s.hot === "warn" ? color.warn : color.main;
      const flash = flashes[n.s.name] ? Math.max(0, 1 - (now - flashes[n.s.name]) / 1500) : 0, a = .35 + n.depth * .65;
      g.globalAlpha = a * .45; g.strokeStyle = hot; g.lineWidth = 1;
      g.beginPath(); g.moveTo(o.x, o.y); g.lineTo(n.x, n.y); g.stroke();
      const dot = 4 + n.depth * 5 + flash * 9;
      g.globalAlpha = a; g.fillStyle = hot; g.shadowColor = hot; g.shadowBlur = 12 + flash * 34;
      g.beginPath(); g.arc(n.x, n.y, dot, 0, TAU); g.fill(); g.shadowBlur = 0;
      ellipse(g, n.x, n.y, dot + 7, dot + 7, -t * 2 + n.i, -t * 2 + n.i + 4, 1.2, hot, a * .8);
      g.textAlign = n.x < o.x ? "right" : "left";
      const lx = n.x + (n.x < o.x ? -18 : 18);
      g.font = `600 ${11 + n.depth * 3}px ui-monospace, Consolas, monospace`; g.fillStyle = hot; g.fillText(n.s.name, lx, n.y - 4);
      g.font = `600 ${13 + n.depth * 4}px system-ui, sans-serif`; g.fillStyle = color.text; g.fillText(n.s.value, lx, n.y + 13);
      g.globalAlpha = 1;
    };
    placed = nodes.map((n) => ({ name: n.s.name, x: n.x, y: n.y }));
    nodes.filter((n) => n.depth < .5).forEach(node);

    // the brain of light
    const lit = tint ? Math.max(0, 1 - (now - tint.born) / tint.hold) : 0;
    // While BRAM's name forms, the threads and core dim so the name can be read.
    const nameAge = name.born ? (now - name.born) / 1000 : 99;
    const hush = nameAge < 4.2 ? Math.min(1, nameAge / .8) * Math.min(1, (4.2 - nameAge) / 1.1) : 0;
    if (tint && !lit) tint = null;
    g.globalCompositeOperation = "lighter";
    const energy = .45 + talking * .55;
    for (const th of threads) {
      const sway = Math.sin(t * th.sp + th.ph) * .35, a = th.a + sway * .25;
      const L = r * 1.6 * th.len * (1 + talking * .15 * Math.sin(t * 8 + th.ph));
      const ex = o.x + Math.cos(a) * L, ey = o.y + Math.sin(a) * L * .9;
      const cx = o.x + Math.cos(a + th.bend + sway) * L * .55, cy = o.y + Math.sin(a + th.bend + sway) * L * .5;
      // A share of the threads take the color of what just happened, more at first.
      const tinted = lit > 0 && (th.ph % 1) < lit * .85;
      g.globalAlpha = (.22 * energy + .1 + (tinted ? lit * .35 : 0)) * (1 - .75 * hush);
      g.strokeStyle = tinted ? tint.color : mood === "ok" ? th.color : base; g.lineWidth = th.width + (tinted ? lit : 0);
      g.beginPath(); g.moveTo(o.x, o.y); g.quadraticCurveTo(cx, cy, ex, ey); g.stroke();
      g.globalAlpha = .7 * energy * (1 - .75 * hush); g.fillStyle = g.strokeStyle;
      g.beginPath(); g.arc(ex, ey, th.width + .6, 0, TAU); g.fill();
    }
    const core = g.createRadialGradient(o.x, o.y, 0, o.x, o.y, r * 1.1);
    core.addColorStop(0, "rgba(255,255,255,.95)"); core.addColorStop(.25, "rgba(150,240,255,.6)"); core.addColorStop(.6, "rgba(90,110,255,.18)"); core.addColorStop(1, "rgba(47,230,255,0)");
    g.globalAlpha = (.7 + .2 * Math.sin(t * 2) + talking * .2) * (1 - .85 * hush); g.fillStyle = core;
    g.beginPath(); g.arc(o.x, o.y, r * 1.1, 0, TAU); g.fill();
    if (lit > 0) {  // the core blooms in that color, then fades back
      const bloom = g.createRadialGradient(o.x, o.y, 0, o.x, o.y, r * (1.3 + (1 - lit) * .8));
      bloom.addColorStop(0, tint.color); bloom.addColorStop(.55, tint.color + "55"); bloom.addColorStop(1, tint.color + "00");
      g.globalAlpha = .75 * lit; g.fillStyle = bloom;
      g.beginPath(); g.arc(o.x, o.y, r * 2.2, 0, TAU); g.fill();
    }
    g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;

    // the voice: rings of glowing dots that wave with it, drifting apart and back together
    let heardNow = 0;
    if (ear) {
      heard ??= new Uint8Array(ear.frequencyBinCount);
      ear.getByteFrequencyData(heard);
      let sum = 0;
      for (let i = 0; i < heard.length / 2; i += 1) sum += heard[i];
      heardNow = Math.min(1, sum / (heard.length / 2) / 110);
    } else if (talking) {
      heardNow = voice.reduce((a, b) => a + b, 0) / Math.max(voice.length, 1);
    }
    level += ((talking || ear ? heardNow : 0) - level) * .18;
    const ringColor = earKind === "listening" ? color.sky : talking ? color.main : base;
    g.globalCompositeOperation = "lighter";
    for (let layer = 0; layer < 4; layer += 1) {
      const dots = 200, wave = r * (.025 + level * .26) * (1 - layer * .12);
      const spread = r * (1.32 + layer * (.05 + level * .07));
      g.fillStyle = ringColor;
      for (let i = 0; i < dots; i += 1) {
        const a = i / dots * TAU;
        const bend = Math.sin(a * 3 + t * 1.7 + layer * 1.3) * .55 + Math.sin(a * 5 - t * 2.3 + layer) * .3
          + Math.sin(a * 9 + t * 3.1 + layer * 2.1) * .15;
        const rr = spread + bend * wave;
        g.globalAlpha = (.32 + level * .5) * (1 - layer * .18) * (.6 + .4 * Math.sin(a * 7 + t * 2));
        g.fillRect(o.x + Math.cos(a) * rr, o.y + Math.sin(a) * rr, 1.6, 1.6);
      }
    }
    g.globalCompositeOperation = "source-over";
    g.globalAlpha = 1;

    // the core: a turning geodesic sphere, brighter while BRAM speaks
    const spinY = t * .35, tiltX = .45 + Math.sin(t * .2) * .15;
    const cy = Math.cos(spinY), sy = Math.sin(spinY), cx = Math.cos(tiltX), sx = Math.sin(tiltX);
    const flat = GEO.points.map(([x, y, z]) => {
      const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
      const y1 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
      return [o.x + x1 * r * .62, o.y + y1 * r * .62, z2];
    });
    g.lineWidth = .8; g.strokeStyle = talking || ear ? color.main : "#7ad7ff";
    for (const [i, j] of GEO.edges) {
      const depth = (flat[i][2] + flat[j][2] + 2) / 4;
      g.globalAlpha = (.08 + depth * .22) * (1 + level * 1.6);
      g.beginPath(); g.moveTo(flat[i][0], flat[i][1]); g.lineTo(flat[j][0], flat[j][1]); g.stroke();
    }
    g.globalAlpha = 1;

    // BRAM's name, forming from dots when it starts to speak, then scattering again
    if (name.born) {
      const age = (now - name.born) / 1000;
      if (age > 4.2) name.born = 0;
      else {
        const gather = Math.min(1, age / 1.1), ease = 1 - Math.pow(1 - gather, 3);
        const leave = Math.max(0, (age - 3.1) / 1.1);
        g.globalCompositeOperation = "lighter"; g.fillStyle = color.main;
        const scale = r * 2.1 / NAME.width;
        for (const d of NAME.dots) {
          const tx = o.x + (d.x - NAME.width / 2) * scale, ty = o.y + (d.y - NAME.height / 2) * scale;
          const x = d.fx * w + (tx - d.fx * w) * ease + d.dx * leave * r, y = d.fy * h + (ty - d.fy * h) * ease + d.dy * leave * r;
          g.globalAlpha = (.35 + .6 * ease) * (1 - leave) * (.7 + .3 * Math.sin(now / 90 + d.ph));
          g.fillRect(x, y, 1.8, 1.8);
        }
        g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
      }
    }

    // callouts: a line draws out from the brain to a labeled reading, like POWER LEVEL 45.4%
    callout(g, o, r, now);

    // pulses running in, and the wave when one arrives
    pulses = pulses.filter((p) => now - p.born < 1400);
    for (const p of pulses) {
      const n = place(p.i, t, o), k = (now - p.born) / 1400;
      g.fillStyle = p.color; g.shadowColor = p.color; g.shadowBlur = 18;
      for (let tail = 0; tail < 7; tail += 1) {
        const kk = Math.max(0, k - tail * .03); g.globalAlpha = (1 - tail / 7) * .95;
        g.beginPath(); g.arc(n.x + (o.x - n.x) * kk, n.y + (o.y - n.y) * kk, 4.5 - tail * .5, 0, TAU); g.fill();
      }
      g.shadowBlur = 0; g.globalAlpha = 1;
      if (k > .97 && !p.landed) { p.landed = true; waves.push({ born: now, color: p.color }); }
    }
    // While something is wrong, rings keep going out: red and often, or amber now and then.
    if (alarm && !still.matches && now - lastAlarm > (alarm === "bad" ? 700 : 2400)) {
      lastAlarm = now;
      waves.push({ born: now, color: alarm === "bad" ? color.bad : color.warn });
    }
    // Thinking: arcs sweep around the brain, faster than it spins.
    if (speed > 1) {
      for (let k = 0; k < 3; k += 1) {
        const a = now / 260 + k * TAU / 3;
        g.globalAlpha = .85; g.strokeStyle = color.main; g.lineWidth = 3; g.shadowColor = color.main; g.shadowBlur = 14;
        g.beginPath(); g.arc(o.x, o.y, r * 1.95, a, a + .7); g.stroke();
        g.beginPath(); g.arc(o.x, o.y, r * 2.15, -a * 1.3, -a * 1.3 + .4); g.stroke();
      }
      g.shadowBlur = 0; g.globalAlpha = 1;
      if (now - lastAlarm > 900 && !alarm) { lastAlarm = now; waves.push({ born: now, color: color.sky }); }
    }
    waves = waves.filter((v) => now - v.born < 1800);
    for (const v of waves) { const k = (now - v.born) / 1800; ellipse(g, o.x, o.y, r * (1.2 + k * 3), r * (1.2 + k * 3), 0, TAU, 3 * (1 - k), v.color, 1 - k); }
    nodes.filter((n) => n.depth >= .5).forEach(node);

    // each side screen is wired to the brain
    const box = canvas().getBoundingClientRect();
    for (const panel of document.querySelectorAll("#hud .side .glass")) {
      const p = panel.getBoundingClientRect();
      if (!p.width || getComputedStyle(panel.parentElement).position !== "absolute") continue;
      const left = p.left - box.left < o.x, px = (left ? p.right : p.left) - box.left, py = p.top - box.top + p.height / 2;
      g.globalAlpha = .2; g.strokeStyle = color.main; g.lineWidth = 1; g.setLineDash([2, 6]);
      g.beginPath(); g.moveTo(px, py); g.lineTo(px + (left ? 40 : -40), py); g.lineTo(o.x + (left ? -r * 2.3 : r * 2.3), o.y + (py - o.y) * .25); g.stroke();
      g.setLineDash([]); g.globalAlpha = .8; g.fillStyle = color.main; g.fillRect(px - 2, py - 2, 4, 4); g.globalAlpha = 1;
    }
    if (!still.matches) {
      const sy = (t * 60) % (h + 200) - 100, scan = g.createLinearGradient(0, sy - 40, 0, sy + 2);
      scan.addColorStop(0, "rgba(47,230,255,0)"); scan.addColorStop(1, "rgba(47,230,255,.06)");
      g.fillStyle = scan; g.fillRect(0, sy - 40, w, 42);
    }
    dials(t);
  }

  // small round instruments on the side screens
  function dialRing(id, share, t, stroke) {
    const c = $(id);
    if (!c || !c.getBoundingClientRect().width) return;
    const d = c.getContext("2d"), s = c.width, m = s / 2;
    d.clearRect(0, 0, s, s); d.lineCap = "round"; d.strokeStyle = stroke;
    d.globalAlpha = .18; d.lineWidth = 10; d.beginPath(); d.arc(m, m, m - 22, 0, TAU); d.stroke();
    d.globalAlpha = 1; d.shadowColor = stroke; d.shadowBlur = 12;
    d.beginPath(); d.arc(m, m, m - 22, -Math.PI / 2, -Math.PI / 2 + Math.max(.005, share) * TAU); d.stroke(); d.shadowBlur = 0;
    d.save(); d.translate(m, m); d.rotate(t * .4);
    for (let i = 0; i < 60; i += 1) { const a = i / 60 * TAU; d.globalAlpha = i % 5 ? .3 : .8; d.lineWidth = i % 5 ? 1 : 2; d.beginPath(); d.moveTo(Math.cos(a) * (m - 6), Math.sin(a) * (m - 6)); d.lineTo(Math.cos(a) * (m - 12), Math.sin(a) * (m - 12)); d.stroke(); }
    d.restore();
    d.globalAlpha = .6; d.lineWidth = 2; d.beginPath(); d.arc(m, m, m - 38, -t, -t + 1.5); d.stroke(); d.globalAlpha = 1;
  }
  function dials(t) {
    const now = new Date();
    dialRing("dial-date", now.getDate() / 31, t, color.main);
    dialRing("dial-time", (now.getMinutes() * 60 + now.getSeconds()) / 3600, -t, color.sky);
    if (outdoor !== null) dialRing("dial-temp", Math.max(0, Math.min(1, (outdoor + 10) / 120)), t * .7, color.warn);
  }

  function loop(time) {
    draw(time);
    frame = !$("deck").hidden && document.body.classList.contains("command") ? requestAnimationFrame(loop) : 0;
  }
  function wake() {
    if (still.matches) draw();
    else if (!frame) frame = requestAnimationFrame(loop);
  }

  // Which system is under a point on the canvas, for clicking one.
  function at(x, y) {
    let best = null, near = 30;
    for (const p of placed) {
      const d = Math.hypot(p.x - x, p.y - y);
      if (d < near) { near = d; best = p.name; }
    }
    return best;
  }

  function start() {
    colors();
    addEventListener("resize", () => draw());
    wake();
  }

  return { at, start, update, orbit, pulse, alert, points, spell, say, think, listen, house, weather, state, colors, draw: () => { draw(); wake(); } };
})();

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
  let w = 0, h = 0, spin = 0, last = 0, speed = 1, frame = 0, mood = "ok";
  let color = {}, dust = [], threads = [], systems = [], pulses = [], waves = [], flashes = {};
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

  // The systems on the orbit: [{name, value, hot: "" | "warn" | "bad"}]
  function orbit(list) { systems = list; }

  // Something happened in one system: it flashes and a pulse runs into the brain.
  function pulse(name, kind = "main") {
    const i = systems.findIndex((s) => s.name === name), now = performance.now();
    flashes[name] = now;
    if (i >= 0) pulses.push({ i, born: now, color: color[kind] || color.main });
    else waves.push({ born: now, color: color[kind] || color.main });
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
    if (node) { talking = 1; state(kind === "listening" ? "listen" : "speak"); }
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

  function center() { return { x: w / 2, y: h * .45, r: Math.min(w * .1, h * .15) }; }

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
    const base = mood === "bad" ? color.bad : mood === "warn" ? color.warn : color.main;
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
    nodes.filter((n) => n.depth < .5).forEach(node);

    // the brain of light
    g.globalCompositeOperation = "lighter";
    const energy = .45 + talking * .55;
    for (const th of threads) {
      const sway = Math.sin(t * th.sp + th.ph) * .35, a = th.a + sway * .25;
      const L = r * 1.6 * th.len * (1 + talking * .15 * Math.sin(t * 8 + th.ph));
      const ex = o.x + Math.cos(a) * L, ey = o.y + Math.sin(a) * L * .9;
      const cx = o.x + Math.cos(a + th.bend + sway) * L * .55, cy = o.y + Math.sin(a + th.bend + sway) * L * .5;
      g.globalAlpha = .22 * energy + .1; g.strokeStyle = mood === "ok" ? th.color : base; g.lineWidth = th.width;
      g.beginPath(); g.moveTo(o.x, o.y); g.quadraticCurveTo(cx, cy, ex, ey); g.stroke();
      g.globalAlpha = .7 * energy; g.fillStyle = g.strokeStyle;
      g.beginPath(); g.arc(ex, ey, th.width + .6, 0, TAU); g.fill();
    }
    const core = g.createRadialGradient(o.x, o.y, 0, o.x, o.y, r * 1.1);
    core.addColorStop(0, "rgba(255,255,255,.95)"); core.addColorStop(.25, "rgba(150,240,255,.6)"); core.addColorStop(.6, "rgba(90,110,255,.18)"); core.addColorStop(1, "rgba(47,230,255,0)");
    g.globalAlpha = .7 + .2 * Math.sin(t * 2) + talking * .2; g.fillStyle = core;
    g.beginPath(); g.arc(o.x, o.y, r * 1.1, 0, TAU); g.fill();
    g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;

    // the voice ring
    let levels = null;
    if (ear) {
      heard ??= new Uint8Array(ear.frequencyBinCount);
      ear.getByteFrequencyData(heard);
      levels = Array.from({ length: 72 }, (_, i) => heard[Math.floor((Math.abs(i - 36) / 36) * heard.length * .5)] / 255);
    }
    for (let i = 0; i < 72; i += 1) {
      const a = i / 72 * TAU - Math.PI / 2;
      const level = levels ? levels[i] : talking ? (voice[i] || 0) : .06 + .05 * Math.sin(t * 3 + i * .5);
      const r1 = r * 1.18, r2 = r1 + r * .55 * level + 2;
      g.strokeStyle = earKind === "listening" ? color.sky : talking ? "#ffffff" : base;
      g.globalAlpha = .45 + level * .55; g.lineWidth = 2;
      g.beginPath(); g.moveTo(o.x + Math.cos(a) * r1, o.y + Math.sin(a) * r1); g.lineTo(o.x + Math.cos(a) * r2, o.y + Math.sin(a) * r2); g.stroke();
    }
    g.globalAlpha = 1;

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

  function start() {
    colors();
    addEventListener("resize", () => draw());
    wake();
  }

  return { start, update, orbit, pulse, say, think, listen, house, weather, state, colors, draw: () => { draw(); wake(); } };
})();

"use strict";
// BRAM's core: rings that turn, gauges that sweep to real values, a voice that breathes,
// and a pulse each time something happens. Words never sit on the rings.
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
  const photos = new Map();
  let speed = 1, spun = 0, lastTime = 0, frame = 0, color = {}, sparks = [], mood = "ok";
  let arcs = [], waves = [], voice = 0;
  const ARC_COLORS = ["main", "warn", "sky", "violet"];

  function colors() {
    const style = getComputedStyle(document.body);
    const read = (name) => style.getPropertyValue(name).trim();
    color = { main: read("--hud"), dim: read("--hud-dim"), warn: read("--hud-warn"), bad: read("--hud-bad"), text: read("--hud-text"), sky: "#7ad7ff", violet: "#b88cff" };
  }

  // --- data ---

  function update(groups) {
    const all = groups.flatMap((group) => group.devices);
    mood = all.some((d) => d.state === "alert") ? "bad" : all.some((d) => d.state === "warn") ? "warn" : "ok";
  }

  // Gauges around the core: [{label, value (0-1), text}]. Their words are listed beside it.
  function gauges(list) {
    arcs = list.slice(0, 4).map((item, i) => {
      const old = arcs.find((arc) => arc.label === item.label);
      return { ...item, shown: old ? old.shown : 0, color: ARC_COLORS[i] };
    });
    $("core-legend").replaceChildren(...arcs.map((arc) => {
      const row = make("div", undefined, `legend ${arc.color}`);
      row.append(make("i"), make("span", arc.label), make("b", arc.text));
      return row;
    }));
  }

  // Something happened: a wave rolls out from the core.
  function pulse(kind = "main") {
    waves.push({ born: performance.now(), kind });
    if (waves.length > 6) waves.shift();
    if (still.matches) draw();
  }

  function photo(source) {
    if (!source) return null;
    if (!photos.has(source)) {
      const image = new Image();
      image.addEventListener("error", () => { image.failed = true; });
      image.src = source;
      photos.set(source, image);
    }
    const image = photos.get(source);
    return image.complete && image.naturalWidth && !image.failed ? image : null;
  }

  function people(list) {
    $("people-pane").hidden = !list.length;
    $("hud-people").replaceChildren(...list.map((person) => {
      const card = make("div", undefined, `face ${person.state}`);
      if (person.photo) {
        const image = make("img");
        image.alt = "";
        image.src = person.photo;
        image.addEventListener("error", () => image.replaceWith(make("i", [...person.name][0])));
        card.append(image);
      } else {
        card.append(make("i", [...person.name][0]));
      }
      card.append(make("b", person.name), make("span", person.state === "unknown" ? "unknown" : person.area || (person.text || person.says).replace(/^at /, "")), make("small", person.age));
      return card;
    }));
  }

  // --- small gauges ---

  function gauge(id, part, whole, label) {
    const box = $(id), share = whole ? part / whole : 0;
    if (!box) return;
    const kind = !whole ? "" : share === 1 ? "ok" : share >= .75 ? "warn" : "bad";
    const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("aria-hidden", "true");
    for (let i = 0; i < 40; i += 1) {
      const angle = (i / 40) * TAU - Math.PI / 2, tick = document.createElementNS(NS, "line");
      const set = (name, value) => tick.setAttribute(name, value.toFixed(2));
      set("x1", 50 + Math.cos(angle) * 37); set("y1", 50 + Math.sin(angle) * 37);
      set("x2", 50 + Math.cos(angle) * 46); set("y2", 50 + Math.sin(angle) * 46);
      if (whole && i < Math.round(share * 40)) tick.setAttribute("class", "lit");
      svg.append(tick);
    }
    const spin = document.createElementNS(NS, "circle");
    spin.setAttribute("cx", "50"); spin.setAttribute("cy", "50"); spin.setAttribute("r", "32"); spin.setAttribute("class", "spin");
    svg.append(spin);
    box.className = `gauge ${kind}`;
    box.replaceChildren(svg, make("b", whole ? `${part}/${whole}` : "--"), make("span", label));
  }

  function activity(times) {
    const hours = new Array(24).fill(0), now = Date.now() / 1000;
    for (const at of times) {
      const age = Math.floor((now - at) / 3600);
      if (age >= 0 && age < 24) hours[23 - age] += 1;
    }
    const top = Math.max(...hours, 1);
    $("hud-activity").replaceChildren(...hours.map((count, i) => {
      const bar = make("i");
      bar.style.height = `${Math.max(3, (count / top) * 100)}%`;
      bar.title = `${count} event${count === 1 ? "" : "s"}, ${23 - i} hours ago`;
      return bar;
    }));
    $("hud-activity-total").textContent = `${hours.reduce((a, b) => a + b, 0)} in 24 h`;
  }

  // --- drawing ---

  const canvas = () => $("scope");
  function size() {
    const node = canvas(), box = node.getBoundingClientRect(), ratio = Math.min(devicePixelRatio || 1, 2);
    if (!box.width) return false;
    if (node.width !== Math.round(box.width * ratio) || node.height !== Math.round(box.height * ratio)) {
      node.width = Math.round(box.width * ratio);
      node.height = Math.round(box.height * ratio);
      sparks = Array.from({ length: 90 }, () => ({ x: Math.random(), y: Math.random(), v: .00008 + Math.random() * .00025, s: Math.random() * 1.5 + .3, a: Math.random() * TAU }));
    }
    node.getContext("2d").setTransform(ratio, 0, 0, ratio, 0, 0);
    return { w: box.width, h: box.height };
  }

  function draw(time = 0) {
    const box = size();
    if (!box) return;
    const g = canvas().getContext("2d"), x = box.w / 2, y = box.h / 2, r = Math.min(box.w, box.h) * .46;
    if (r < 50) return;
    if (time && lastTime) spun += Math.max(0, Math.min(time - lastTime, 100)) / 1000 * speed;
    if (time) lastTime = time;
    const t = still.matches ? 0 : spun, now = performance.now();
    const base = mood === "bad" ? color.bad : mood === "warn" ? color.warn : color.main;
    g.clearRect(0, 0, box.w, box.h);
    g.lineCap = "round";

    // drifting dust
    for (const spark of sparks) {
      if (!still.matches) { spark.y = (spark.y - spark.v + 1) % 1; spark.a += .01; }
      g.globalAlpha = .25 + .25 * Math.sin(spark.a);
      g.fillStyle = color.main;
      g.fillRect(spark.x * box.w, spark.y * box.h, spark.s, spark.s);
    }

    const ring = (radius, width, alpha, from = 0, to = TAU, stroke = base, dash = null) => {
      g.globalAlpha = alpha;
      g.strokeStyle = stroke;
      g.lineWidth = width;
      g.setLineDash(dash || []);
      g.beginPath();
      g.arc(x, y, radius, from, to);
      g.stroke();
      g.setLineDash([]);
    };

    // outer scales, turning at different speeds and directions
    ring(r, 1, .25);
    g.save();
    g.translate(x, y);
    g.rotate(t * .05);
    for (let i = 0; i < 180; i += 1) {
      const a = (i / 180) * TAU, long = i % 15 === 0, inner = r * (long ? .925 : .95);
      g.globalAlpha = long ? .8 : .35;
      g.strokeStyle = base;
      g.lineWidth = long ? 2 : 1;
      g.beginPath();
      g.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
      g.lineTo(Math.cos(a) * r * .98, Math.sin(a) * r * .98);
      g.stroke();
    }
    g.restore();
    ring(r * 1.03, 3, .6, -t * .12, -t * .12 + 1.1);
    ring(r * 1.03, 3, .6, -t * .12 + 2.4, -t * .12 + 2.9);
    ring(r * 1.03, 3, .6, -t * .12 + 4.1, -t * .12 + 5.3);
    ring(r * .9, 1, .4, 0, TAU, base, [2, 10]);

    // gauges sweep toward their values
    arcs.forEach((arc, i) => {
      arc.shown += (arc.value - arc.shown) * (still.matches ? 1 : .04);
      const radius = r * (.82 - i * .075), stroke = color[arc.color] || base;
      ring(radius, 9, .12, 0, TAU, stroke);
      const end = -Math.PI / 2 + Math.max(.002, arc.shown) * TAU;
      ring(radius, 9, .95, -Math.PI / 2, end, stroke);
      g.globalAlpha = 1;
      g.fillStyle = stroke;
      g.shadowColor = stroke;
      g.shadowBlur = 14;
      g.beginPath();
      g.arc(x + Math.cos(end) * radius, y + Math.sin(end) * radius, 5, 0, TAU);
      g.fill();
      g.shadowBlur = 0;
    });

    // inner turning arcs
    const inner = r * .42;
    ring(inner, 5, .9, t * .6, t * .6 + 1.6);
    ring(inner, 5, .9, t * .6 + Math.PI, t * .6 + Math.PI + 1.6);
    ring(inner * .86, 2, .6, -t * .9, -t * .9 + 2.6);
    ring(inner * .72, 1, .45, t * 1.3, t * 1.3 + 4.2);

    // a sweep of light
    if (!still.matches) {
      const a = t * .7, grad = g.createRadialGradient(x, y, inner, x, y, r * .9);
      grad.addColorStop(0, "transparent");
      grad.addColorStop(1, base);
      g.globalAlpha = .08;
      g.fillStyle = grad;
      g.beginPath();
      g.moveTo(x, y);
      g.arc(x, y, r * .9, a, a + .5);
      g.closePath();
      g.fill();
    }

    // the voice: breathing when idle, lively while thinking or speaking
    voice += ((speed > 1 ? 1 : .22) - voice) * .05;
    const bars = 19, width = inner * 1.15, step = width / bars;
    for (let i = 0; i < bars; i += 1) {
      const middle = 1 - Math.abs(i - (bars - 1) / 2) / (bars / 2);
      const wave = still.matches ? .5 : .35 + .65 * Math.abs(Math.sin(now / 420 * (1 + i % 4 * .3) + i * 1.7));
      const h = Math.max(4, inner * 1.1 * middle * wave * voice + 4);
      g.globalAlpha = .55 + .45 * middle;
      g.fillStyle = base;
      g.shadowColor = base;
      g.shadowBlur = 10;
      g.fillRect(x - width / 2 + i * step + step * .2, y - h / 2, step * .6, h);
    }
    g.shadowBlur = 0;

    // pulses from things that happened
    waves = waves.filter((wave) => now - wave.born < 2600);
    for (const wave of waves) {
      const life = (now - wave.born) / 2600;
      ring(inner + (r - inner) * life, 3 * (1 - life), 1 - life, 0, TAU, color[wave.kind] || base);
    }
    g.globalAlpha = 1;
  }

  function loop(time) {
    draw(time);
    frame = requestAnimationFrame(loop);
  }

  function start() {
    colors();
    addEventListener("resize", () => draw());
    if (still.matches) draw();
    if (!frame && !still.matches) frame = requestAnimationFrame(loop);
  }

  return { start, update, gauge, gauges, pulse, activity, colors, draw, people, think: (on) => { speed = on ? 4 : 1; } };
})();

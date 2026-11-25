"use strict";
// The command deck: a live picture of the house. Every mark on it is a real device or event.
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
  let speed = 1, spun = 0, lastTime = 0;
  let sectors = [], nodes = [], chosen = null, hover = null, frame = 0, color = {}, sparks = [], mood = "ok";

  function colors() {
    const style = getComputedStyle(document.body);
    const read = (name) => style.getPropertyValue(name).trim();
    color = { main: read("--hud"), dim: read("--hud-dim"), warn: read("--hud-warn"), bad: read("--hud-bad"), text: read("--hud-text") };
  }

  // --- data ---

  function update(groups) {
    sectors = groups.filter((group) => group.devices.length);
    if (!sectors.some((group) => group.title === chosen)) chosen = null;
    nodes = [];
    const total = sectors.reduce((sum, group) => sum + Math.max(group.devices.length, 2), 0) || 1;
    let at = -Math.PI / 2;
    for (const group of sectors) {
      const span = (Math.max(group.devices.length, 2) / total) * TAU;
      Object.assign(group, { from: at, to: at + span });
      const rows = Math.max(1, Math.ceil(group.devices.length / Math.max(1, Math.floor(span * 9))));
      group.devices.forEach((device, i) => {
        const row = i % rows, place = (Math.floor(i / rows) + .5) / Math.ceil(group.devices.length / rows);
        nodes.push({ ...device, group: group.title, angle: at + span * (.08 + .84 * place), depth: rows === 1 ? .5 : row / (rows - 1) });
      });
      at += span;
    }
    const bad = nodes.filter((node) => node.state === "alert").length;
    mood = bad ? "bad" : nodes.some((node) => node.state === "warn") ? "warn" : "ok";
    list();
  }

  function list() {
    $("hud-sectors").replaceChildren(...sectors.map((group) => {
      const row = make("button", undefined, "sector"), bar = make("span", undefined, "segments");
      row.type = "button";
      row.setAttribute("aria-pressed", String(chosen === group.title));
      bar.append(...group.devices.slice(0, 24).map((device) => make("i", undefined, device.state)));
      const on = group.devices.filter((device) => device.state !== "off" && device.state !== "unknown").length;
      const name = make("b", group.title);
      if (group.floor) name.append(make("small", ` ${group.floor}`));
      if (group.presence === "occupied") name.append(make("em", "occupied"));
      row.append(name, make("span", `${on}/${group.devices.length}`, "num"), bar);
      row.addEventListener("click", () => {
        chosen = chosen === group.title ? null : group.title;
        list();
        draw();
      });
      return row;
    }));
    const group = sectors.find((item) => item.title === chosen);
    const shown = group ? group.devices : nodes.filter((node) => node.state !== "off");
    $("hud-detail-title").textContent = group ? group.title : "Active now";
    $("hud-detail").replaceChildren(...(shown.length ? shown.slice(0, 60).map((device) => {
      const row = make("li", undefined, device.state), left = make("span", device.name);
      const more = [device.text, device.area, device.age].filter(Boolean).join(" \u00b7 ");
      if (more) left.append(make("small", more));
      row.append(left, make("b", device.state === "unknown" ? "unknown" : device.says));
      return row;
    }) : [make("li", "Nothing active")]));
  }

  // --- people ---

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

  // --- gauges ---

  function gauge(id, part, whole, label) {
    const box = $(id), share = whole ? part / whole : 0;
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
      sparks = Array.from({ length: 70 }, () => ({ x: Math.random(), y: Math.random(), v: .00012 + Math.random() * .0003, s: Math.random() * 1.6 + .3 }));
    }
    node.getContext("2d").setTransform(ratio, 0, 0, ratio, 0, 0);
    return { w: box.width, h: box.height };
  }

  function place(node, view) {
    const r = view.inner + (view.outer - view.inner) * (.16 + .68 * node.depth);
    return { x: view.x + Math.cos(node.angle) * r, y: view.y + Math.sin(node.angle) * r };
  }

  function layout(box) {
    const r = Math.min(box.w * .5 - 92, box.h * .5 - 44);
    return { x: box.w / 2, y: box.h / 2, r, inner: r * .4, outer: r * .9 };
  }

  function tint(node) {
    return { alert: color.bad, warn: color.warn, on: color.main }[node.state] || color.dim;
  }

  function draw(time = 0) {
    const box = size();
    if (!box) return;
    const g = canvas().getContext("2d"), view = layout(box), { x, y, r } = view;
    if (r < 60) return;
    // Spins faster while BRAM thinks, without jumping.
    if (time && lastTime) spun += Math.max(0, Math.min(time - lastTime, 100)) / 1000 * speed;
    if (time) lastTime = time;
    const t = still.matches ? 0 : spun;
    const base = mood === "bad" ? color.bad : color.main;
    g.clearRect(0, 0, box.w, box.h);
    g.lineCap = "butt";
    const ring = (radius, width, alpha, from = 0, to = TAU, stroke = base) => {
      g.globalAlpha = alpha;
      g.strokeStyle = stroke;
      g.lineWidth = width;
      g.beginPath();
      g.arc(x, y, radius, from, to);
      g.stroke();
    };
    // drifting motes
    g.fillStyle = base;
    for (const spark of sparks) {
      if (!still.matches) spark.y = (spark.y - spark.v + 1) % 1;
      g.globalAlpha = .12 + .25 * Math.abs(Math.sin(spark.x * 40 + t));
      g.fillRect(spark.x * box.w, spark.y * box.h, spark.s, spark.s);
    }
    // glow
    const halo = g.createRadialGradient(x, y, r * .05, x, y, r * 1.05);
    halo.addColorStop(0, base);
    halo.addColorStop(1, "transparent");
    g.globalAlpha = .13;
    g.fillStyle = halo;
    g.beginPath();
    g.arc(x, y, r * 1.05, 0, TAU);
    g.fill();
    // rings
    for (const [scale, alpha] of [[.4, .35], [.58, .16], [.74, .16], [.9, .35]]) ring(r * scale, 1, alpha);
    for (let i = 0; i < 180; i += 1) {
      const angle = (i / 180) * TAU, long = i % 15 === 0;
      g.globalAlpha = long ? .7 : .28;
      g.strokeStyle = base;
      g.lineWidth = 1;
      g.beginPath();
      g.moveTo(x + Math.cos(angle) * r * .95, y + Math.sin(angle) * r * .95);
      g.lineTo(x + Math.cos(angle) * r * (long ? 1 : .975), y + Math.sin(angle) * r * (long ? 1 : .975));
      g.stroke();
    }
    ring(r * .36, 5, .8, t * .5, t * .5 + 1.5);
    ring(r * .36, 5, .8, t * .5 + Math.PI, t * .5 + Math.PI + 1.5);
    ring(r * .32, 2, .6, -t * .8, -t * .8 + 2.4);
    ring(r * .28, 1, .5, t * 1.2, t * 1.2 + 4.4);
    ring(r * 1.03, 2, .5, -t * .15, -t * .15 + .9);
    ring(r * 1.03, 2, .5, -t * .15 + 2.2, -t * .15 + 2.7);
    ring(r * 1.03, 2, .5, -t * .15 + 4, -t * .15 + 5.2);
    // sweep
    const sweep = t * .7;
    for (let i = 0; i < 26; i += 1) {
      g.globalAlpha = .11 * (1 - i / 26);
      g.fillStyle = base;
      g.beginPath();
      g.moveTo(x + Math.cos(sweep - i * .03) * view.inner, y + Math.sin(sweep - i * .03) * view.inner);
      g.arc(x, y, view.outer, sweep - i * .03, sweep - i * .03 - .032, true);
      g.arc(x, y, view.inner, sweep - i * .03 - .032, sweep - i * .03);
      g.fill();
    }
    // sectors
    g.font = "600 11px ui-monospace, Consolas, monospace";
    for (const group of sectors) {
      const picked = chosen === group.title;
      g.globalAlpha = .3;
      g.strokeStyle = base;
      g.lineWidth = 1;
      g.beginPath();
      g.moveTo(x + Math.cos(group.from) * view.inner, y + Math.sin(group.from) * view.inner);
      g.lineTo(x + Math.cos(group.from) * view.outer, y + Math.sin(group.from) * view.outer);
      g.stroke();
      if (picked || group.presence === "occupied") {
        g.globalAlpha = picked ? .12 : .07;
        g.fillStyle = base;
        g.beginPath();
        g.arc(x, y, view.outer, group.from, group.to);
        g.arc(x, y, view.inner, group.to, group.from, true);
        g.fill();
      }
      const mid = (group.from + group.to) / 2, lx = x + Math.cos(mid) * r * 1.09, ly = y + Math.sin(mid) * r * 1.09;
      const worst = group.devices.some((d) => d.state === "alert") ? color.bad : group.devices.some((d) => d.state === "warn") ? color.warn : color.text;
      g.globalAlpha = picked ? 1 : .85;
      g.fillStyle = worst;
      g.textAlign = Math.abs(Math.cos(mid)) < .25 ? "center" : Math.cos(mid) > 0 ? "left" : "right";
      g.textBaseline = "middle";
      // Long names take two lines, so none runs off the edge.
      const parts = group.title.toUpperCase().split(" AND ");
      parts.forEach((part, i) => g.fillText(i ? `& ${part}` : part, lx, ly + (i - (parts.length - 1) / 2) * 13));
    }
    // devices
    for (const node of nodes) {
      const spot = place(node, view), faded = chosen && node.group !== chosen && node.state !== "alert";
      const passed = ((sweep - node.angle) % TAU + TAU) % TAU;
      const lit = still.matches ? .4 : Math.max(0, 1 - passed / 1.6);
      g.globalAlpha = faded ? .15 : 1;
      if (node.state === "alert") {
        g.strokeStyle = color.bad;
        g.lineWidth = 1.5;
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(spot.x, spot.y);
        g.stroke();
        for (const wave of [0, .5]) {
          const grow = (t * .9 + wave) % 1;
          g.globalAlpha = (1 - grow) * (faded ? .2 : .9);
          g.beginPath();
          g.arc(spot.x, spot.y, 5 + grow * 26, 0, TAU);
          g.stroke();
        }
        g.globalAlpha = 1;
      }
      const big = node.state === "alert" ? 6 : node.state === "off" || node.state === "unknown" ? 3 : 4.5;
      g.fillStyle = tint(node);
      g.strokeStyle = tint(node);
      g.lineWidth = 1.2;
      if (!faded) g.globalAlpha = node.state === "off" ? .45 + lit * .55 : 1;
      const face = photo(node.photo);
      if (face) {
        g.save();
        g.beginPath();
        g.arc(spot.x, spot.y, 15, 0, TAU);
        g.clip();
        g.globalAlpha *= node.state === "on" ? 1 : .45;
        g.drawImage(face, spot.x - 15, spot.y - 15, 30, 30);
        g.restore();
        g.beginPath();
        g.arc(spot.x, spot.y, 15, 0, TAU);
        g.lineWidth = 2;
        g.stroke();
      }
      g.beginPath();
      g.arc(spot.x, spot.y, big, 0, TAU);
      if (face) {
        // the photo is the mark
      } else if (node.state === "unknown") {
        g.setLineDash([2, 2]);
        g.stroke();
        g.setLineDash([]);
      } else {
        g.shadowColor = tint(node);
        g.shadowBlur = 6 + lit * 14;
        g.fill();
        g.shadowBlur = 0;
      }
      if (node === hover || node.state === "alert" || node.state === "warn" || (chosen && node.group === chosen && nodes.length < 60)) {
        const label = [node.name, node.state === "unknown" ? "unknown" : node.says, node === hover && node.text, node === hover && node.age].filter(Boolean).join("  ");
        const right = spot.x >= x;
        g.globalAlpha = faded ? .15 : 1;
        g.font = "600 11px ui-monospace, Consolas, monospace";
        g.textAlign = right ? "left" : "right";
        const lx = spot.x + (right ? 22 : -22), ly = spot.y - 14;
        g.beginPath();
        g.moveTo(spot.x, spot.y);
        g.lineTo(spot.x + (right ? 12 : -12), ly);
        g.lineTo(lx, ly);
        g.stroke();
        const width = Math.min(g.measureText(label).width, 300) + 12;
        g.fillStyle = "rgb(2 8 18 / .82)";
        g.fillRect(right ? lx : lx - width, ly - 9, width, 18);
        g.strokeRect(right ? lx : lx - width, ly - 9, width, 18);
        g.fillStyle = tint(node) === color.dim ? color.text : tint(node);
        g.fillText(label, lx + (right ? 6 : -6), ly + 1, 300);
      }
    }
    g.globalAlpha = 1;
  }

  function loop(time) {
    frame = requestAnimationFrame(loop);
    if (document.hidden || !canvas().offsetParent) return;
    draw(time);
  }

  function point(event) {
    const box = canvas().getBoundingClientRect(), view = layout({ w: box.width, h: box.height });
    const px = event.clientX - box.left, py = event.clientY - box.top;
    let best = null, near = 16;
    for (const node of nodes) {
      const spot = place(node, view), far = Math.hypot(spot.x - px, spot.y - py);
      if (far < near) { near = far; best = node; }
    }
    return best;
  }

  function start() {
    colors();
    canvas().addEventListener("pointermove", (event) => { hover = point(event); if (still.matches) draw(); });
    canvas().addEventListener("pointerleave", () => { hover = null; });
    canvas().addEventListener("click", (event) => {
      const node = point(event);
      chosen = node ? node.group : null;
      list();
      draw();
    });
    addEventListener("resize", () => draw());
    if (still.matches) draw();
    if (!frame && !still.matches) frame = requestAnimationFrame(loop);
  }

  return { start, update, gauge, activity, colors, draw, people, think: (on) => { speed = on ? 5 : 1; } };
})();

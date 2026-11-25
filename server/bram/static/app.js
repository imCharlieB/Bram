"use strict";
const $ = (id) => document.getElementById(id);
const PAGES = ["overview", "messages", "settings", "findings", "history", "log", "profile"];
// Places inside a page.
const PLACES = { homes: "settings", model: "settings", personality: "settings", voice: "settings", monitors: "messages" };
const STORY = {
  connected: "Home Assistant connected", disconnected: "Home Assistant disconnected", paired: "A home was paired",
  unpaired: "A home was removed", "signed in": "You signed in", "login refused": "Someone entered a wrong login",
  "setup refused": "A setup attempt was refused", "settings saved": "Settings changed", "login created": "Your login was created",
  "code created": "A pairing code was made", "password changed": "Your password changed", "history saved": "History settings changed", "history cleaned": "History was cleaned up", "history deleted": "History was deleted", "database damaged": "The database failed its check", "second factor on": "Second factor turned on", "second factor off": "Second factor turned off", "username changed": "Your username changed",
  "signed out others": "Other devices were signed out", "monitor added": "A monitor was added", "monitor removed": "A monitor was removed",
};
const ALARMING = new Set(["login refused", "setup refused", "disconnected", "alert", "send failed"]);
let paired = false, modelSaved = false, signedIn = false, oldest = null;

// --- helpers ---

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  let response, data;
  try {
    response = await fetch("/api/" + path, options);
    data = await response.json();
  } catch {
    throw new Error("The BRAM Server did not answer");
  }
  if (response.status === 401) show("login");
  if (!response.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

function show(name) {
  signedIn = name === "app";
  if (!signedIn) $("chat-log").replaceChildren();
  if (!signedIn) document.body.classList.remove("on-deck");
  for (const id of ["setup", "closed", "login", "app"]) $(id).hidden = id !== name;
}

function say(id, text, kind = "") {
  $(id).textContent = text;
  $(id).className = "message " + kind;
}

function element(tag, text, kind) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (kind) node.className = kind;
  return node;
}

async function busy(button, messageId, work) {
  button.disabled = true;
  say(messageId, "Working...");
  try {
    say(messageId, (await work()) || "", "good");
  } catch (error) {
    say(messageId, error.message, "bad");
  } finally {
    button.disabled = false;
  }
}

function onSubmit(form, button, messageId, work) {
  $(form).addEventListener("submit", (event) => {
    event.preventDefault();
    busy($(button), messageId, work);
  });
}

function onClick(button, messageId, work) {
  $(button).addEventListener("click", () => busy($(button), messageId, work));
}

function askPassword(text) {
  const box = $("confirm"), form = $("confirm-form");
  $("confirm-text").textContent = text;
  $("confirm-password").value = "";
  box.showModal();
  return new Promise((resolve, reject) => {
    let password = null;
    form.onsubmit = (event) => {
      event.preventDefault();
      password = $("confirm-password").value;
      box.close();
    };
    $("confirm-cancel").onclick = () => box.close();
    box.onclose = () => {
      $("confirm-password").value = "";
      if (password === null) reject(new Error("Cancelled"));
      else resolve(password);
    };
  });
}

// --- loading ---

function loadSteps() {
  const steps = [["Create your login", true, "#profile"], ["Connect Home Assistant", paired, "#homes"],
    ["Choose a model", modelSaved, "#model"]];
  $("start").hidden = steps.every(([, done]) => done);
  $("steps").replaceChildren(...steps.map(([text, done, link]) => {
    const row = element("li"), go = element("a", "Set up");
    go.href = link;
    row.append(element("span", text), done ? element("span", "Done", "good") : go);
    return row;
  }));
}

// Fixes (0.12.1) may differ between the two sides; features (0.12) should not.
const release = (text) => text.split(".").slice(0, 2).join(".");

async function loadStatus() {
  const { houses, version } = await api("status");
  $("version").textContent = `BRAM Server ${version}`;
  paired = houses.length > 0;
  loadSteps();
  world.houses = houses;
  const odd = houses.find((house) => house.connected && release(house.version) !== release(version));
  $("outdated").hidden = !odd;
  if (odd) {
    const old = !odd.version || odd.version.localeCompare(version, undefined, { numeric: true }) < 0;
    $("outdated-text").textContent = `The BRAM Server is ${version}, but BRAM in Home Assistant (${odd.name}) is ${odd.version || "older"}. `
      + (old ? "In HACS, update BRAM, then restart Home Assistant." : "In Portainer, recreate the bram container with Re-pull image turned on.");
  }
  dots("home-houses", houses.map((house) => [house.name, house.connected, house.connected ? "Connected" : "Not connected"]));
  $("houses").replaceChildren(...(houses.length ? houses.map((house) => {
    const row = element("li"), side = element("span"), remove = element("button", "Remove", "quiet small");
    remove.addEventListener("click", () => busy(remove, "pair-message", async () => {
      const confirm = await askPassword(`Remove ${house.name}? It will need a new code to return.`);
      await api("unpair", { house_id: house.id, confirm });
      await loadStatus();
      return "Removed";
    }));
    side.append(element("span", house.connected ? "Connected" : "Not connected", house.connected ? "good" : "bad"), remove);
    row.append(element("span", house.name), side);
    return row;
  }) : [element("li", "None yet")]));
}

function logText(entry) {
  return `${entry.trigger}: ${entry.reason}`;
}

function ago(at) {
  const minutes = Math.round((Date.now() / 1000 - at) / 60);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) return `${Math.round(minutes / 60)} hr ago`;
  return new Date(at * 1000).toLocaleDateString();
}

async function loadLatest() {
  const { entries } = await api("log?limit=6");
  $("latest").replaceChildren(...(entries.length ? entries.map((entry) => {
    const row = element("li", undefined, ALARMING.has(entry.decision) ? "alarming" : "");
    row.append(element("span", STORY[entry.decision] || entry.reason), element("span", ago(entry.at), "note"));
    return row;
  }) : [element("li", "Quiet so far")]));
}

async function loadLog(more = false) {
  const query = new URLSearchParams({ limit: 50, kind: $("log-kind").value });
  if (more && oldest !== null) query.set("before", oldest);
  const { entries } = await api("log?" + query);
  const rows = entries.map((entry) => {
    const row = element("tr");
    row.append(element("td", new Date(entry.at * 1000).toLocaleString()), element("td", entry.house),
      element("td", entry.decision.replaceAll("_", " ")), element("td", logText(entry)));
    return row;
  });
  if (more) $("log").append(...rows);
  else $("log").replaceChildren(...rows);
  if (entries.length) oldest = entries.at(-1).id;
  $("older").hidden = entries.length < 50;
  return $("log").children.length ? "" : "Nothing here yet";
}

function fillModels(names, chosen) {
  const list = [...names];
  if (chosen && !list.includes(chosen)) list.unshift(chosen);
  $("model").replaceChildren(...list.map((name) => {
    const option = element("option", name);
    option.value = name;
    option.selected = name === chosen;
    return option;
  }));
}

function personality() {
  const chosen = document.querySelector("#modes input:checked");
  return { personality: chosen ? chosen.value : "professional", custom_style: $("custom").value };
}

async function loadSettings() {
  const { settings, modes, custom_limit } = await api("settings");
  modelSaved = Boolean(settings.model);
  loadSteps();
  $("tile-model").textContent = settings.model || "Not chosen";
  $("tile-personality").textContent = modes.find((mode) => mode.id === settings.personality)?.name || "";
  $("moods").replaceChildren(...modes.filter((mode) => mode.id !== "custom").map((mode) => {
    const chip = element("button", mode.name, mode.id === settings.personality ? "chip on" : "chip");
    chip.addEventListener("click", () => busy(chip, "overview-message", async () => {
      await api("settings", { personality: mode.id });
      await loadSettings();
    }));
    return chip;
  }));
  $("url").value = settings.model_url;
  $("context").value = settings.context;
  fillModels([], settings.model);
  $("custom").value = settings.custom_style;
  $("custom").maxLength = custom_limit;
  $("modes").replaceChildren(...modes.map((mode) => {
    const label = element("label"), input = element("input");
    input.type = "radio";
    input.name = "mode";
    input.value = mode.id;
    input.checked = mode.id === settings.personality;
    label.append(input, element("b", mode.name), element("span", mode.about));
    return label;
  }));
  $("custom-box").hidden = settings.personality !== "custom";
}

async function loadProfile() {
  const { user, sessions, factor } = await api("profile");
  showFactor(factor);
  for (const id of ["nav-user", "profile-user"]) $(id).textContent = user;
  for (const id of ["avatar", "avatar-big"]) $(id).textContent = ([...user][0] || "?").toUpperCase();
  $("sessions").textContent = sessions === 1 ? "this device only" : `${sessions} devices`;
}

async function loadMonitors() {
  const { monitors } = await api("monitors");
  world.monitors = monitors;
  dots("home-monitors", monitors.map((item) => [item.name, item.up, item.up === null ? "Checking" : item.up ? "Answering" : "Not answering"]));
  $("monitor-list").replaceChildren(...(monitors.length ? monitors.map((item) => {
    const row = element("li"), side = element("span"), remove = element("button", "Remove", "quiet small");
    remove.addEventListener("click", () => busy(remove, "monitors-message", async () => {
      await api("monitor-remove", { id: item.id });
      await loadMonitors();
      return "Removed";
    }));
    const [text, kind] = item.up === null ? ["Checking", "note"] : item.up ? ["Answering", "good"] : ["Not answering", "bad"];
    side.append(element("span", text, kind), remove);
    const left = element("span", item.name), type = { ollama: "Ollama", frigate: "Frigate", device: "Device" }[item.kind];
    left.append(element("span", `${type} at ${item.url}${item.reason ? `: ${item.reason}` : ""}`, "note sub"));
    row.append(left, side);
    return row;
  }) : [element("li", "None yet")]));
}

function hourSelect(value, label) {
  const select = element("select");
  select.setAttribute("aria-label", label);
  for (let hour = -1; hour < 24; hour += 1) {
    const option = element("option", hour < 0 ? "Off" : new Date(2000, 0, 1, hour).toLocaleTimeString([], { hour: "numeric" }));
    option.value = hour;
    option.selected = hour === (value ?? -1);
    select.append(option);
  }
  return select;
}

function quietRow(channel, quiet, messageId) {
  const row = document.querySelector(`.quiet-row[data-channel=${channel}]`);
  const from = hourSelect(quiet.from, "Quiet from"), to = hourSelect(quiet.to, "Quiet until");
  const save = element("button", "Save quiet hours", "quiet small");
  save.addEventListener("click", () => busy(save, messageId, async () => {
    const start = Number(from.value), end = Number(to.value);
    const off = start < 0 || end < 0;
    await api("quiet", {
      channel, from: off ? null : start, to: off ? null : end,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    });
    return off ? "Quiet hours are off" : "Saved";
  }));
  row.replaceChildren(element("label", "Quiet hours"), from, element("span", "to"), to, save);
}

async function loadMessages() {
  const { ntfy, telegram, muted } = await api("messages");
  const state = (id, ready) => { $(id).textContent = ready ? "On" : "Off"; $(id).className = ready ? "good" : "note"; };
  state("tg-state", telegram.on && telegram.linked);
  $("tg-on").checked = telegram.on;
  $("tg-chat").checked = telegram.chat;
  $("tg-token").value = "";
  $("tg-token").placeholder = telegram.token_saved ? `Saved (${telegram.bot})` : "";
  $("tg-link").textContent = telegram.linked ? "Link a different account" : "Link my account";
  state("ntfy-state", ntfy.on && ntfy.topic);
  $("ntfy-on").checked = ntfy.on;
  $("ntfy-url").value = ntfy.url;
  $("ntfy-phone").value = ntfy.phone_url || `http://${location.hostname}:2586`;
  $("ntfy-server").textContent = ntfy.phone_url;
  $("ntfy-topic").textContent = ntfy.topic;
  $("ntfy-help").hidden = !ntfy.link;
  if (ntfy.link) {
    $("ntfy-link").href = ntfy.link;
    $("ntfy-qr").src = "/api/ntfy-qr?" + encodeURIComponent(ntfy.topic);
  }
  quietRow("telegram", telegram.quiet, "tg-message");
  quietRow("ntfy", ntfy.quiet, "ntfy-message");
  $("muted").replaceChildren(...(muted.length ? muted.map((item) => {
    const row = element("li"), undo = element("button", "Allow again", "quiet small");
    undo.addEventListener("click", () => busy(undo, "messages-message", async () => {
      await api("unmute", { house_id: item.house_id, key: item.key });
      await loadMessages();
    }));
    row.append(element("span", `${item.house}: ${item.key}`), undo);
    return row;
  }) : [element("li", "None")]));
}

async function saveNtfy(extra = {}) {
  const confirm = await askPassword("This is where BRAM sends your alerts.");
  await api("ntfy", {
    confirm, on: $("ntfy-on").checked, url: $("ntfy-url").value, phone_url: $("ntfy-phone").value, ...extra,
  });
  await loadMessages();
}

// --- home ---

const world = { houses: [], monitors: [], urgent: 0, devices: 0, groups: [], rooms: new Map() };

function dots(id, items) {
  $(id).replaceChildren(...(items.length ? items.map(([name, good, text]) => {
    const row = element("li"), left = element("span");
    left.append(element("i", undefined, good === null ? "dot" : good ? "dot up" : "dot down"), name);
    row.append(left, element("span", text, "note"));
    return row;
  }) : [element("li", "Nothing yet")]));
}

function headline(problem) {
  const hour = new Date().getHours(), user = $("nav-user").textContent;
  $("hello").textContent = `Good ${hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening"}, ${user}`;
  const down = [...world.houses.filter((house) => !house.connected), ...world.monitors.filter((item) => item.up === false)];
  $("hero").classList.toggle("worried", Boolean(problem) || down.length > 0 || world.urgent > 0);
  $("hud-pulse").textContent = problem ? "No signal" : world.urgent ? "Alert" : down.length ? "Attention" : "Watching";
  document.body.classList.toggle("worried-deck", Boolean(problem) || down.length > 0 || world.urgent > 0);
  $("hud-pulse").className = problem || world.urgent ? "bad" : down.length ? "amber" : "";
  if (world.urgent && !problem) {
    $("headline").textContent = world.urgent === 1 ? "A safety sensor needs you" : `${world.urgent} safety sensors need you`;
    $("detail").textContent = "See Alerts. Home Assistant has messaged your phones if you set that up.";
  } else if (problem) {
    $("headline").textContent = "I can't see clearly";
    $("detail").textContent = problem;
  } else if (!world.houses.length) {
    $("headline").textContent = "Let's get connected";
    $("detail").textContent = "I can't see a home yet.";
  } else if (down.length) {
    $("headline").textContent = down.length === 1 ? `${down[0].name} isn't answering` : `${down.length} things aren't answering`;
    $("detail").textContent = down.map((item) => item.name).join(", ");
  } else {
    $("headline").textContent = "Everything I watch is answering";
    $("detail").textContent = `${world.houses.length} home${world.houses.length === 1 ? "" : "s"}, ${world.monitors.length} monitor${world.monitors.length === 1 ? "" : "s"}. Leaks and other home alerts come straight from Home Assistant.`;
  }
}

function bubble(role, text, facts = []) {
  const box = element("div", undefined, `bubble ${role}`);
  box.append(element("p", text));
  if (facts.length) {
    const list = element("ul", undefined, "facts");
    list.append(...facts.map((fact) => element("li", fact)));
    box.append(list);
  }
  $("chat-log").append(box);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
  $("chat-clear").hidden = false;
  return box;
}

// --- voice ---

const MAX_TALK = 30000;
let player = null, playing = null, recording = null;

async function loadVoice() {
  const voice = await api("speech");
  $("voice-hear").value = voice.hear;
  $("voice-speak").value = voice.speak;
  voiceName = voice.voice;
  for (const [id, address] of [["hear", voice.hear], ["speak", voice.speak]]) {
    $(`${id}-dot`).className = address ? "dot up" : "dot";
    $(`${id}-state`).textContent = address ? `On, using ${address}` : "Not set up";
  }
  const on = Boolean(voice.hear || voice.speak);
  $("voice-find").textContent = on ? "Look again" : "Set up voice";
  $("voice-tests").hidden = !on;
  $("voice-test").hidden = !voice.speak;
  $("hear-test").hidden = !voice.hear;
  $("voice-choose").hidden = $("voice-missing").hidden = true;
  $("talk").hidden = !voice.hear;
  $("aloud-box").hidden = !voice.speak;
}

let voiceName = "";

function showVoices(voices) {
  const language = (navigator.language || "en").slice(0, 2).toLowerCase();
  const mine = voices.filter((voice) => voice.language.toLowerCase().startsWith(language));
  const list = mine.length ? mine : voices;
  const options = [["", "Piper's own choice"], ...list.map((voice) => [voice.name, `${voice.ready ? "" : "\u2601 "}${voice.name.replaceAll("_", " ").replaceAll("-", " ")}`])];
  $("voice-list").replaceChildren(...options.map(([value, text]) => {
    const option = element("option", text);
    option.value = value;
    option.selected = value === voiceName;
    return option;
  }));
  $("voice-pick").hidden = !$("voice-speak").value;
}

function showFound(hear, speak) {
  const set = (id, found) => {
    $(`${id}-dot`).className = found ? "dot up" : "dot down";
    $(`${id}-state`).textContent = found ? `Found at ${found}` : "Not found";
  };
  set("hear", hear);
  set("speak", speak);
  $("voice-choose").hidden = !hear && !speak;
  $("voice-missing").hidden = Boolean(hear && speak);
}

function hush() {
  if (playing) playing.stop();
  playing = null;
}

async function play(path, body) {
  player ??= new AudioContext();
  await player.resume();
  const response = await fetch("/api/" + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error((await response.json()).error || "BRAM could not speak");
  const sound = await player.decodeAudioData(await response.arrayBuffer());
  hush();
  playing = player.createBufferSource();
  playing.buffer = sound;
  playing.connect(player.destination);
  playing.start();
}

const speak = (text) => play("speak", { text: text.slice(0, 1500) });

async function openMicrophone() {
  if (!navigator.mediaDevices) throw new Error("This browser only allows the microphone over https");
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
  } catch {
    throw new Error("The microphone was not allowed");
  }
  const context = new AudioContext(), parts = [];
  const stop = async () => {
    for (const track of stream.getTracks()) track.stop();
    await context.close();
    return toPcm(parts, context.sampleRate);
  };
  try {
    await context.audioWorklet.addModule("recorder.js");
    const node = new AudioWorkletNode(context, "recorder");
    node.port.onmessage = (event) => parts.push(event.data);
    context.createMediaStreamSource(stream).connect(node);
  } catch (error) {
    await stop();
    throw error;
  }
  return stop;
}

// To 16 kHz, 16-bit, mono.
function toPcm(parts, rate) {
  const all = new Float32Array(parts.reduce((sum, part) => sum + part.length, 0));
  let at = 0;
  for (const part of parts) { all.set(part, at); at += part.length; }
  const step = rate / 16000, out = new Int16Array(Math.min(Math.floor(all.length / step), 480000));
  for (let i = 0; i < out.length; i += 1) {
    const from = Math.floor(i * step), to = Math.max(from + 1, Math.floor((i + 1) * step));
    let sum = 0;
    for (let j = from; j < to; j += 1) sum += all[j];
    out[i] = Math.max(-1, Math.min(1, sum / (to - from))) * 32767;
  }
  return out;
}

function talkStart(button, messageId, done) {
  if (recording || $("chat-send").disabled) return;
  hush();
  player ??= new AudioContext();  // created by a press, so the browser lets it play later
  player.resume();
  button.classList.add("live");
  say(messageId, "Listening. Let go when you are done.");
  const opening = openMicrophone();
  opening.catch(() => {});
  recording = { opening, button, messageId, done, timer: setTimeout(talkStop, MAX_TALK) };
}

async function talkStop() {
  if (!recording) return;
  const { opening, button, messageId, done, timer } = recording;
  recording = null;
  clearTimeout(timer);
  button.classList.remove("live");
  button.disabled = true;
  try {
    const pcm = await (await opening)();
    if (pcm.length < 4000) throw new Error("Hold the button while you speak");
    say(messageId, "Working out what you said...");
    const response = await fetch("/api/hear", { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm });
    const data = await response.json();
    if (response.status === 401) show("login");
    if (!response.ok) throw new Error(data.error || "Something went wrong");
    if (!data.text) throw new Error("I didn't catch that");
    say(messageId, "");
    done(data.text);
  } catch (error) {
    say(messageId, error.message, "bad");
  } finally {
    button.disabled = false;
  }
}

function holdToTalk(button, messageId, done) {
  const begin = () => talkStart(button, messageId, done);
  button.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    button.setPointerCapture(event.pointerId);
    begin();
  });
  for (const name of ["pointerup", "pointercancel"]) button.addEventListener(name, talkStop);
  button.addEventListener("keydown", (event) => {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    if (!event.repeat) begin();
  });
  button.addEventListener("keyup", (event) => {
    if (event.key === " " || event.key === "Enter") talkStop();
  });
  button.addEventListener("contextmenu", (event) => event.preventDefault());
}

async function loadChat() {
  const { messages } = await api("chat");
  $("chat-log").replaceChildren();
  $("chat-clear").hidden = true;
  for (const message of messages) bubble(message.role, message.text);
}

const TITLES = {
  leak: "Safety", smoke: "Safety", co: "Safety", gas: "Safety", heat: "Safety", hazard: "Safety",
  lock: "Locks and doors", opening: "Locks and doors", person: "People", motion: "Motion", light: "Lights",
  switch: "Switches and fans", fan: "Switches and fans", media: "Media", satellite: "Voice",
  climate: "Climate", temperature: "Climate", humidity: "Climate", other: "Other",
};
const ORDER = ["Safety", "Locks and doors", "People", "Motion", "Climate", "Lights", "Switches and fans", "Media", "Voice", "Other"];

let byRoom = false;

function arrange() {
  $("hud-by").textContent = byRoom ? "by room" : "by type";
  $("hud-by").title = byRoom ? "Show by type" : "Show by room";
  if (!byRoom) return deck.update(world.groups);
  const rooms = new Map();
  for (const device of world.groups.flatMap((group) => group.devices)) {
    const floor = device.floor || "", room = device.area || (device.kind === "person" ? (device.state === "on" ? "Home" : "Away") : "No room");
    if (!rooms.has(room)) rooms.set(room, { title: room, floor, devices: [] });
    if (floor) rooms.get(room).floor = floor;
    rooms.get(room).presence = world.rooms.get(room)?.state || "";
    rooms.get(room).devices.push(device);
  }
  // Rooms on the same floor sit together.
  const last = ["Home", "Away", "No room"];
  return deck.update([...rooms.values()].sort((a, b) => last.indexOf(a.title) - last.indexOf(b.title)
    || a.floor.localeCompare(b.floor) || a.title.localeCompare(b.title)));
}

const PRINTER = { printing: "Printing", paused: "Paused", finished: "Finished", failed: "Failed", stopped: "Stopped", idle: "Idle", off: "Off", unknown: "Unknown" };

function showPrinters(list) {
  $("printers-pane").hidden = !list.length;
  $("hud-printers").replaceChildren(...list.map((printer) => {
    const row = element("li", undefined, `printer ${printer.problem ? "failed" : printer.state}`), head = element("div");
    head.append(element("b", printer.name || "Printer"), element("span", PRINTER[printer.state] + ("progress" in printer && printer.state !== "finished" ? ` ${printer.progress}%` : "")));
    row.append(head);
    if (printer.state === "printing" || printer.state === "paused") {
      const bar = element("progress");
      bar.max = 100;
      if ("progress" in printer) bar.value = printer.progress;
      bar.setAttribute("aria-label", `${printer.name} progress`);
      row.append(bar);
    }
    const heat = (key, word) => key in printer ? `${word} ${printer[key]}${printer[key + "_target"] ? " / " + printer[key + "_target"] : ""}${printer.unit || ""}` : "";
    const line = [printer.file, "left" in printer && `${lasted(printer.left)} left`].filter(Boolean).join(", ");
    if (line) row.append(element("p", line));
    const temps = [heat("nozzle", "nozzle"), heat("nozzle2", "left"), heat("bed", "bed"), heat("chamber", "chamber")].filter(Boolean).join(", ");
    if (temps) row.append(element("small", temps));
    if (printer.problem) row.append(element("small", "Reports a problem"));
    return row;
  }));
}

async function loadHouse() {
  const { homes, alerts, printers, rooms: occupancy } = await api("house");
  showPrinters(printers);
  world.rooms = new Map(occupancy.map((room) => [room.room, room]));
  const groups = new Map(), urgent = [];
  let total = 0, unseen = 0;
  for (const home of homes) {
    for (const device of home.devices) {
      total += 1;
      if (device.state === "unknown") unseen += 1;
      if (device.state === "alert") urgent.push(`${device.name}: ${device.says}`);
      const title = TITLES[device.kind] || "Other";
      if (!groups.has(title)) groups.set(title, []);
      const photo = device.picture ? `/api/picture?${new URLSearchParams({ home: home.id, id: device.id, v: device.picture })}` : "";
      groups.get(title).push({ ...device, photo, age: device.since && device.state !== "unknown" ? ago(device.since) : "" });
    }
  }
  const devices = [...groups.values()].flat();
  world.groups = ORDER.filter((title) => groups.has(title)).map((title) => ({ title, devices: groups.get(title) }));
  arrange();
  deck.people(devices.filter((device) => device.kind === "person"));
  deck.gauge("g-seen", total - unseen, total, "Seen");
  const shut = devices.filter((device) => device.kind === "lock" || device.kind === "opening");
  deck.gauge("g-secure", shut.filter((device) => device.state === "off").length, shut.length, "Secured");
  world.devices = total;
  const rows = [...urgent.map((text) => [text, "now", true]),
    ...alerts.map((alert) => [alert.text, ago(alert.created), Boolean(alert.safety)])];
  $("alert-count").textContent = rows.length ? String(rows.length) : "";
  $("alerts-panel").classList.toggle("red", rows.some(([, , bad]) => bad));
  $("open-alerts").replaceChildren(...(rows.length ? rows.map(([text, when, bad]) => {
    const row = element("li", undefined, bad ? "bad" : "");
    row.append(element("span", text), element("span", when, "note"));
    return row;
  }) : [element("li", "Nothing needs you", "note")]));
  world.urgent = urgent.length;
}

function setLook(look) {
  const command = look !== "classic";
  document.body.classList.toggle("command", command);
  // One chat and one alert list, moved to where the look wants them.
  if (command) {
    $("slot-chat").append($("chat"));
    $("slot-alerts").append($("start"), $("alerts-panel"));
  } else {
    $("hero").after($("alerts-panel"), $("chat"), $("start"));
  }
  for (const chip of document.querySelectorAll("#looks button")) chip.classList.toggle("on", chip.dataset.look === (command ? "command" : "classic"));
  deck.draw();
}

function setHue(hue) {
  document.body.dataset.hue = hue;
  for (const chip of document.querySelectorAll("#hues button")) chip.classList.toggle("on", chip.dataset.hue === hue);
  deck.colors();
  deck.draw();
}

function tick() {
  $("clock").textContent = new Date().toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit" });
}

async function loadLinks() {
  const links = [...world.houses.map((house) => [house.name, house.connected]), ...world.monitors.map((item) => [item.name, item.up])];
  deck.gauge("g-up", links.filter(([, good]) => good).length, links.length, "Links up");
  dots("hud-systems", links.map(([name, good]) => [name, good, good === null ? "checking" : good ? "up" : "down"]));
  $("hud-moods").replaceChildren(...[...$("moods").children].map((chip) => {
    const copy = chip.cloneNode(true);
    copy.addEventListener("click", () => chip.click());
    return copy;
  }));
  const { entries } = await api("log?limit=200");
  deck.activity(entries.map((entry) => entry.at));
  $("hud-term").replaceChildren(...entries.slice(0, 40).map((entry) => {
    const row = element("li", undefined, ALARMING.has(entry.decision) ? "alarming" : "");
    const when = element("time", new Date(entry.at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    row.append(when, STORY[entry.decision] || entry.reason);
    return row;
  }));
}

async function loadHome() {
  let problem = "";
  try {
    await Promise.all([loadStatus(), loadMonitors(), loadSettings(), loadLatest(), loadHouse()]);
    await loadLinks();
  } catch (error) {
    problem = error.message;
  }
  headline(problem);
  $("hud-headline").textContent = $("headline").textContent;
  $("hud-sub").textContent = problem || world.urgent ? $("detail").textContent : world.devices ? `${$("hello").textContent}. Watching ${world.devices} devices.` : "Nothing is shared yet. In Home Assistant: BRAM, Configure, Recommended setup.";
}

setInterval(() => {
  const home = signedIn && !document.hidden && !$("deck").hidden;
  if (home) loadHome();
}, 15000);
setInterval(tick, 1000);

const lasted = (seconds) => seconds >= 3600 ? `${Math.floor(seconds / 3600)} h ${Math.round(seconds % 3600 / 60)} min` : `${Math.round(seconds / 60)} min`;

function cells(values) {
  const row = element("tr");
  row.append(...values.map((value) => element("td", value)));
  return row;
}

async function loadCleanup() {
  const { devices, plans } = await api("cleanup");
  $("clean-plans").replaceChildren(...plans.map((plan) => {
    const row = element("li"), side = element("span"), yes = element("button", "Confirm", "small"), no = element("button", "Cancel", "quiet small");
    yes.addEventListener("click", () => busy(yes, "clean-message", async () => {
      const confirm = await askPassword(`${plan.text}. This cannot be undone.`);
      await api("cleanup-apply", { id: plan.id, confirm });
      await loadHistory();
      return "Done.";
    }));
    no.addEventListener("click", () => busy(no, "clean-message", async () => {
      await api("cleanup-drop", { id: plan.id });
      await loadCleanup();
    }));
    side.append(yes, no);
    row.append(element("span", `${plan.text}. Frees about ${(plan.bytes / 1e6).toFixed(1)} MB.`), side);
    return row;
  }));
  $("clean-devices").replaceChildren(...devices.map((device) => {
    const row = cells(["", device.name + (device.keep ? "" : " (not kept)"), device.area || "", device.rows.toLocaleString(),
      `${(device.bytes / 1e6).toFixed(1)} MB`, device.first ? new Date(device.first * 1000).toLocaleDateString() : ""]);
    const box = element("input");
    box.type = "checkbox";
    box.value = device.id;
    box.setAttribute("aria-label", device.name);
    row.firstChild.append(box);
    return row;
  }));
}

async function loadHistory() {
  await loadCleanup();
  const data = await api("history");
  $("history-on").checked = data.on;
  $("history-limit").value = data.limit_mb;
  const { reading, hourly, change, run } = data.counts;
  $("history-size").textContent = `Using ${(data.size / 1e6).toFixed(1)} MB: ${(reading + hourly).toLocaleString()} readings, ${change.toLocaleString()} changes, ${run.toLocaleString()} heating and cooling runs.`
    + (data.shortened ? " The limit was reached, so the oldest readings are now hourly." : "")
    + (data.healthy ? "" : " THE DATABASE FAILED ITS CHECK. Restore a backup.");
  const days = data.homes.flatMap((home) => home.days), pairs = data.homes.flatMap((home) => home.compare);
  $("history-days").replaceChildren(...days.map((day) => cells([
    new Date(day.day + "T12:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }), day.name,
    Object.entries(day.seconds).map(([what, time]) => `${what} ${lasted(time)}`).join(", ") + (day.cut ? " (not all seen)" : ""),
    Object.entries(day.targets).sort((a, b) => b[1] - a[1]).map(([set, time]) => `${set} for ${lasted(time)}`).join(", "),
    day.starts, day.outside ?? "unknown"])));
  $("history-compare").replaceChildren(...pairs.map((pair) => cells([
    pair.area, `${pair.climate}: ${pair.climate_avg}${pair.unit}`, `${pair.sensor}: ${pair.sensor_avg}${pair.unit}`,
    `${pair.apart > 0 ? "+" : ""}${pair.apart}${pair.unit}`, `${pair.most}${pair.unit}`])));
  const prints = data.homes.flatMap((home) => home.prints);
  $("prints-card").hidden = !prints.length;
  $("history-prints").replaceChildren(...prints.map((print) => cells([new Date(print.end * 1000).toLocaleString(), print.printer, print.file || "unknown",
    print.result + (print.result !== "finished" && print.progress !== null ? ` at ${print.progress}%` : ""), print.whole ? lasted(print.end - print.start) : "not all seen",
    print.weight !== null ? `${print.weight} g` : ""])));
  if (!days.length) $("history-days").append(cells(["Nothing recorded yet"]));
  if (!pairs.length) $("history-compare").append(cells(["Share a thermostat and a temperature sensor in the same room"]));
}

const WHAT = { open: "Found", closed: "Over", sent: "Told", "not sent": "Could not be sent", acked: "Acknowledged", stopped: "Stopped", snoozed: "Snoozed" };
const FROM = { safety: "Safety", silent: "Silent sensor", rules: "Locks and doors", security: "Security", monitors: "Monitor", connection: "Connection", message: "Message", learning: "Learning", problems: "Problem", printers: "Printer" };
let lastFinding = null;

function findingRow(item) {
  const row = element("li", undefined, item.severity), head = element("div", undefined, "head"), side = element("span");
  const told = item.told ? `told ${ago(item.told)}` : "not told", over = item.closed && !item.is_open ? `, over ${ago(item.closed)}` : "";
  const story = element("button", "Story", "quiet small"), hide = element("button", item.ignored ? "Stop ignoring" : "Ignore", "quiet small");
  const list = element("ol");
  list.hidden = true;
  story.addEventListener("click", () => busy(story, "findings-message", async () => {
    list.hidden = !list.hidden;
    if (list.hidden) return;
    const data = await api("finding?id=" + item.id);
    list.replaceChildren(...data.story.map((part) => element("li", `${new Date(part.at * 1000).toLocaleString()}: ${WHAT[part.what] || part.what}. ${part.text}`)));
  }));
  hide.addEventListener("click", () => busy(hide, "findings-message", async () => {
    await api("finding-ignore", { id: item.id, on: !item.ignored });
    return loadFindings();
  }));
  side.append(story, hide);
  head.append(element("b", item.text), side);
  row.append(head, element("span", `${FROM[item.source] || item.source}${item.home ? ", " + item.home : ""}: ${item.times === 1 ? "once" : item.times + " times"}, first ${ago(item.first)}, last ${ago(item.last)}, ${told}${item.acked ? ", acknowledged" : ""}${item.stopped ? ", messages stopped" : ""}${over}`, "note"), list);
  return row;
}

async function loadFindings(more = false) {
  const show = $("findings-show").value, query = new URLSearchParams({ show });
  if (more && lastFinding !== null) query.set("before", lastFinding);
  const { findings } = await api("findings?" + query);
  if (more) $("findings").append(...findings.map(findingRow));
  else $("findings").replaceChildren(...findings.map(findingRow));
  if (findings.length) lastFinding = findings.at(-1).last;
  $("findings-older").hidden = findings.length < 50;
  return $("findings").children.length ? "" : show === "open" ? "Nothing open that BRAM checks for." : "Nothing here.";
}

// --- pages ---

const LOADERS = {
  overview: () => Promise.all([loadChat(), loadVoice(), loadHome()]),
  settings: () => Promise.all([loadStatus(), loadSettings(), loadVoice()]),
  messages: () => Promise.all([loadMonitors(), loadMessages()]),
  findings: async () => say("findings-message", await loadFindings()), history: loadHistory,
  log: async () => say("log-message", await loadLog()), profile: loadProfile,
};
const MESSAGES = {
  overview: "overview-message", settings: "pair-message", messages: "messages-message",
  findings: "findings-message", history: "history-message", log: "log-message", profile: "session-message",
};

async function openPage() {
  if (!signedIn) return;
  const wanted = location.hash.slice(1), page = PLACES[wanted] || (PAGES.includes(wanted) ? wanted : "overview");
  for (const section of document.querySelectorAll("[data-page]")) section.hidden = section.dataset.page !== page;
  for (const link of document.querySelectorAll("nav a:not(.brand)")) {
    if (link.hash === "#" + page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  document.body.classList.toggle("on-deck", page === "overview");
  // Never leave a pairing code or a typed password behind.
  $("code-box").hidden = true;
  $("code").textContent = "";
  $("sample").hidden = true;
  $("tg-link-box").hidden = true;
  $("change-form").reset();
  $("factor-codes").hidden = true;
  $("factor-recovery").textContent = "";
  for (const node of document.querySelectorAll("#pages .message")) say(node.id, "");
  scrollTo(0, 0);
  try {
    await LOADERS[page]();
    if (PLACES[wanted]) $("at-" + wanted).scrollIntoView();
  } catch (error) {
    say(MESSAGES[page], error.message, "bad");
  }
}

async function start() {
  const state = await api("state");
  if (!state.login_exists) return show(state.setup_open ? "setup" : "closed");
  if (!state.signed_in) return show("login");
  show("app");
  await loadProfile();
  await openPage();
}

addEventListener("hashchange", openPage);

// --- actions ---

onSubmit("setup-form", "create", "setup-message", async () => {
  const password = $("new-password").value;
  if (password !== $("new-again").value) throw new Error("The passwords do not match");
  await api("setup", { user: $("new-user").value, password });
  $("setup-form").reset();
  await start();
});

onSubmit("login-form", "signin", "login-message", async () => {
  const { need_code } = await api("login", {
    user: $("user").value, password: $("password").value, code: $("login-code").value,
  });
  if (need_code) {
    $("login-code-box").hidden = false;
    $("login-code").focus();
    return "Enter your code";
  }
  $("login-form").reset();
  $("login-code-box").hidden = true;
  await start();
});

onSubmit("pair-form", "pair", "pair-message", async () => {
  const confirm = await askPassword("This lets a Home Assistant connect to BRAM.");
  const { code, minutes } = await api("pair", { name: $("home").value, confirm });
  $("code").textContent = code;
  $("address").textContent = location.hostname;
  $("port").textContent = location.port || "443";
  $("minutes").textContent = minutes;
  $("code-box").hidden = false;
});

$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("code").textContent);
    say("pair-message", "Copied", "good");
  } catch {
    say("pair-message", "Select the code and copy it by hand", "bad");
  }
});

onSubmit("chat-form", "chat-send", "chat-message", async () => {
  const text = $("chat-text").value.trim();
  if (!text) return "";
  const mine = bubble("user", text);
  $("chat-text").value = "";
  document.body.classList.add("thinking");
  deck.think(true);
  try {
    const reply = await api("chat", { text, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
    bubble("assistant", reply.text, reply.facts);
    if ($("aloud").checked && !$("aloud-box").hidden) speak(reply.text).catch((error) => say("chat-message", error.message, "bad"));
  } catch (error) {
    mine.remove();
    if (!$("chat-text").value) $("chat-text").value = text;
    throw error;
  } finally {
    document.body.classList.remove("thinking");
    deck.think(false);
    $("chat-text").focus();
  }
});
holdToTalk($("talk"), "chat-message", (text) => {
  $("chat-text").value = text;
  $("chat-form").requestSubmit();
});
holdToTalk($("hear-test"), "voice-message", (text) => say("voice-message", `I heard: ${text}`, "good"));
addEventListener("blur", talkStop);
try { $("aloud").checked = localStorage.getItem("aloud") === "yes"; } catch { /* not remembered */ }
$("aloud").addEventListener("change", () => {
  if (!$("aloud").checked) hush();
  try { localStorage.setItem("aloud", $("aloud").checked ? "yes" : "no"); } catch { /* not remembered */ }
});
onClick("voice-find", "voice-message", async () => {
  const { hear, speak: voice } = await api("speech-find", { host: location.hostname });
  if (hear) $("voice-hear").value = hear.address;
  if (voice) $("voice-speak").value = voice.address;
  showFound(hear?.address || $("voice-hear").value, voice?.address || $("voice-speak").value);
  showVoices(voice?.voices || []);
  return hear || voice ? "Choose a voice, listen, then turn it on." : "";
});
onClick("voice-load", "voice-message", async () => {
  const { voices } = await api("speech-voices", { address: $("voice-speak").value });
  showFound($("voice-hear").value, $("voice-speak").value);
  showVoices(voices);
  return "Now press Turn on voice.";
});
onClick("voice-preview", "voice-message", async () => {
  await play("speech-preview", { address: $("voice-speak").value, voice: $("voice-list").value });
});
onClick("voice-save", "voice-message", async () => {
  const confirm = await askPassword("Your voice will be sent to these machines on your network.");
  await api("speech", { confirm, hear: $("voice-hear").value, speak: $("voice-speak").value, voice: $("voice-list").value || "" });
  await loadVoice();
  return "Voice is on. Test it above, or hold the talk button on Home.";
});
onClick("voice-off", "voice-message", async () => {
  const confirm = await askPassword("Turn off hearing and speaking?");
  await api("speech", { confirm, hear: "", speak: "", voice: "" });
  await loadVoice();
  return "Voice is off.";
});
onClick("voice-test", "voice-message", async () => {
  await speak("Good evening. This is BRAM.");
  return "You should hear BRAM now";
});
for (const chip of document.querySelectorAll("#looks button")) {
  chip.addEventListener("click", () => {
    setLook(chip.dataset.look);
    try { localStorage.setItem("look", chip.dataset.look); } catch { /* not remembered */ }
  });
}
for (const chip of document.querySelectorAll("#hues button")) {
  chip.addEventListener("click", () => {
    setHue(chip.dataset.hue);
    try { localStorage.setItem("hue", chip.dataset.hue); } catch { /* not remembered */ }
  });
}
$("hud-by").addEventListener("click", () => {
  byRoom = !byRoom;
  arrange();
  try { localStorage.setItem("by", byRoom ? "room" : "type"); } catch { /* not remembered */ }
});
try { byRoom = localStorage.getItem("by") === "room"; } catch { /* by type */ }
arrange();
try { setHue(localStorage.getItem("hue") || "cyan"); } catch { setHue("cyan"); }
try { setLook(localStorage.getItem("look") || "command"); } catch { setLook("command"); }
tick();
deck.start();
onClick("chat-clear", "chat-message", async () => {
  await api("chat-clear", {});
  await loadChat();
});

onClick("find", "model-message", async () => {
  const { models } = await api("models", { url: $("url").value });
  fillModels(models, models.includes($("model").value) ? $("model").value : models[0]);
  return models.length ? `Found ${models.length}` : "No local models found there";
});

onClick("save-model", "model-message", async () => {
  const confirm = await askPassword("The model will see what BRAM says about your home.");
  await api("settings", {
    confirm, model_url: $("url").value, model: $("model").value, context: Number($("context").value),
  });
  return "Saved";
});

$("monitor-kind").addEventListener("change", () => {
  $("monitor-url").placeholder = {
    ollama: "http://HOST:11434", frigate: "https://HOST:8971", device: "HOST:80",
  }[$("monitor-kind").value] || "HOST:PORT";
});
onSubmit("monitor-form", "monitor-add", "monitor-message", async () => {
  await api("monitors", {
    kind: $("monitor-kind").value, name: $("monitor-name").value, url: $("monitor-url").value,
  });
  $("monitor-form").reset();
  await loadMonitors();
  return "Added";
});
onClick("tg-save", "tg-message", async () => {
  const confirm = await askPassword("This is where BRAM sends your alerts.");
  await api("telegram", { confirm, on: $("tg-on").checked, chat: $("tg-chat").checked, token: $("tg-token").value });
  await loadMessages();
  return "Saved";
});
onClick("tg-remove", "tg-message", async () => {
  const confirm = await askPassword("Remove the Telegram bot from BRAM?");
  await api("telegram", { confirm, remove: true });
  await loadMessages();
  return "Removed";
});
onClick("tg-link", "tg-message", async () => {
  const confirm = await askPassword("The account that opens this link will get your alerts.");
  $("tg-url").href = (await api("telegram-link", { confirm })).url;
  $("tg-link-box").hidden = false;
});
for (const [button, channel] of [["tg-test", "telegram"], ["ntfy-test", "ntfy"]]) {
  onClick(button, channel === "ntfy" ? "ntfy-message" : "tg-message", async () => {
    await api("test-message", { channel });
    return "Sent";
  });
}
onClick("ntfy-copy", "ntfy-message", async () => {
  await navigator.clipboard.writeText($("ntfy-topic").textContent);
  return "Copied";
});
onClick("ntfy-save", "ntfy-message", async () => { await saveNtfy(); return "Saved"; });
onClick("ntfy-new", "ntfy-message", async () => {
  await saveNtfy({ new_topic: true });
  return "New topic made. Subscribe to it on your phone.";
});

$("modes").addEventListener("change", () => {
  $("custom-box").hidden = personality().personality !== "custom";
});

onClick("save-personality", "personality-message", async () => {
  await api("settings", personality());
  return "Saved";
});

onClick("try", "personality-message", async () => {
  $("sample").hidden = true;
  const { text } = await api("sample", personality());
  $("sample").textContent = text || "(The model said nothing)";
  $("sample").hidden = false;
});

onSubmit("history-form", "history-save", "history-message", async () => {
  const confirm = await askPassword("This changes what BRAM remembers about your home.");
  await api("history", { confirm, on: $("history-on").checked, limit_mb: Number($("history-limit").value),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
  await loadHistory();
  return $("history-on").checked ? "Saved." : "Saved. What was kept is still here until you delete it.";
});

onClick("clean-plan", "clean-message", async () => {
  const devices = [...$("clean-devices").querySelectorAll("input:checked")].map((box) => Number(box.value));
  await api("cleanup-plan", { action: $("clean-action").value, devices, older_days: $("clean-age").value ? Number($("clean-age").value) : null });
  await loadCleanup();
  return "Check the list above, then confirm it.";
});

onClick("clean-later", "clean-message", async () => {
  await api("cleanup-later", {});
  return "I will ask again in 30 days if it is still nearly full.";
});

onClick("history-delete", "history-message", async () => {
  const confirm = await askPassword("Delete everything BRAM recorded about your devices? This cannot be undone.");
  await api("history-delete", { confirm });
  await loadHistory();
  return "Deleted.";
});

onClick("findings-refresh", "findings-message", () => loadFindings());
onClick("findings-older", "findings-message", () => loadFindings(true));
$("findings-show").addEventListener("change", () => busy($("findings-refresh"), "findings-message", () => loadFindings()));
onClick("refresh", "log-message", () => loadLog());
onClick("older", "log-message", () => loadLog(true));
$("log-kind").addEventListener("change", () => busy($("refresh"), "log-message", () => loadLog()));

onSubmit("name-form", "rename", "name-message", async () => {
  const confirm = await askPassword("Enter your password to change your username.");
  await api("username", { new: $("name-new").value, confirm });
  $("name-form").reset();
  await loadProfile();
  return "Changed. Every other device has been signed out.";
});

let factorOn = false;

function showFactor(on) {
  factorOn = on;
  $("factor-note").textContent = on
    ? "On. Signing in needs a code from your phone. To turn it off, enter a code."
    : "Off. Add a code from an authenticator app to signing in. BRAM will need this before it can control anything.";
  $("factor-start").hidden = on;
  $("factor-form").hidden = !on;
  $("factor-go").textContent = on ? "Turn off" : "Turn on";
  $("factor-setup").hidden = true;
  $("factor-secret").textContent = "";
  $("factor-qr").removeAttribute("src");
  $("factor-form").reset();
}

onClick("factor-start", "factor-message", async () => {
  const confirm = await askPassword("This adds a second step to signing in.");
  const { secret } = await api("factor-start", { confirm });
  $("factor-secret").textContent = secret;
  $("factor-qr").src = "/api/factor-qr?" + Date.now();
  $("factor-setup").hidden = $("factor-form").hidden = false;
  $("factor-start").hidden = true;
});

onSubmit("factor-form", "factor-go", "factor-message", async () => {
  const code = $("factor-code").value;
  if (factorOn) {
    const confirm = await askPassword("Turn off the second factor?");
    await api("factor-off", { confirm, code });
    $("factor-codes").hidden = true;
    showFactor(false);
    return "Turned off.";
  }
  const { recovery } = await api("factor-on", { code });
  showFactor(true);
  $("factor-recovery").textContent = recovery.join("\n");
  $("factor-codes").hidden = false;
  return "Turned on. Every other device has been signed out.";
});

onSubmit("change-form", "change", "change-message", async () => {
  const password = $("change-new").value;
  if (password !== $("change-again").value) throw new Error("The passwords do not match");
  const confirm = await askPassword("Enter your current password.");
  await api("password", { new: password, confirm });
  $("change-form").reset();
  await loadProfile();
  return "Changed. Every other device has been signed out.";
});

$("logout").addEventListener("click", async () => {
  hush();
  $("chat-log").replaceChildren();
  try { await api("logout", {}); } finally { location.assign("/ui/"); }
});

onClick("logout-others", "session-message", async () => {
  await api("logout-others", {});
  await loadProfile();
  return "Every other device has been signed out.";
});

start().catch((error) => { show("login"); say("login-message", error.message, "bad"); });

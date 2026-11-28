"use strict";
const $ = (id) => document.getElementById(id);
const PAGES = ["overview", "messages", "settings", "findings", "history", "log", "profile"];
// Places inside a page.
const PLACES = { homes: "settings", model: "settings", personality: "settings", voice: "settings", cameras: "settings", router: "settings", memory: "settings", monitors: "messages" };
const STORY = {
  connected: "Home Assistant connected", disconnected: "Home Assistant disconnected", paired: "A home was paired",
  unpaired: "A home was removed", "signed in": "You signed in", "login refused": "Someone entered a wrong login",
  "setup refused": "A setup attempt was refused", "settings saved": "Settings changed", "login created": "Your login was created",
  "code created": "A pairing code was made", "password changed": "Your password changed", "history saved": "History settings changed", "history cleaned": "History was cleaned up", "history deleted": "History was deleted", "database damaged": "The database failed its check", "second factor on": "Second factor turned on", "second factor off": "Second factor turned off", "username changed": "Your username changed",
  "signed out others": "Other devices were signed out", "monitor added": "A monitor was added", "frigate connected": "Frigate was connected", "frigate removed": "Frigate was disconnected", "camera on": "A camera was turned on", "router connected": "Your router was connected", "memory on": "Memory was turned on", "memory off": "Memory was turned off", "memory forgotten": "Everything remembered was forgotten", "router removed": "Your router was disconnected", "camera off": "A camera was turned off", "monitor removed": "A monitor was removed",
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
  $("nav-version").textContent = `v${version}`;
  // What is running, on Home: the server, and BRAM in each connected Home Assistant.
  const there = houses.filter((house) => house.connected && house.version);
  const apart = there.some((house) => release(house.version) !== release(version));  // fixes may differ
  $("hud-version").textContent = [`Server ${version}`, ...there.map((house) => `${houses.length > 1 ? house.name : "HA"} ${house.version}`)].join(" · ");
  $("hud-version").classList.toggle("apart", apart);
  $("hud-version").title = apart ? "The two halves of BRAM are on different versions. Update both." : "What is running";
  paired = houses.length > 0;
  loadSteps();
  for (const house of houses) {
    const was = world.houses.find((h) => h.id === house.id);
    if (!house.connected && (!was || was.connected)) {
      seen.downSince = { ...(seen.downSince || {}), [house.id]: Date.now() };
      popUp(`house:${house.id}`, "bad", "Connection", `${houses.length > 1 ? house.name : "Home Assistant"} isn't connected`,
        "BRAM can't see your home or send its messages until it's back. Usually Home Assistant is restarting.");
    } else if (house.connected && was && !was.connected) {
      closePop(`house:${house.id}`);
      popUp(`house-back:${house.id}:${Date.now()}`, "good", "Connection", `${houses.length > 1 ? house.name : "Home Assistant"} is back`);
    }
  }
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
  for (const item of monitors) {
    const before = world.monitors.find((m) => m.id === item.id);
    if (before && before.up !== false && item.up === false) {
      popUp(`monitor:${item.id}`, "bad", "Monitor down", `${item.name} is not answering.`, item.reason || "", { href: "#monitors", label: "Monitors" });
    } else if (before && before.up === false && item.up) {
      closePop(`monitor:${item.id}`);
      popUp(`monitor-back:${item.id}:${Date.now()}`, "good", "Monitor back", `${item.name} is answering again.`);
    }
  }
  world.monitors = monitors;
  $("monitors-pane").hidden = !monitors.length;
  const upCount = monitors.filter((item) => item.up).length;
  $("monitors-count").textContent = monitors.length ? `${upCount} of ${monitors.length} up` : "";
  $("hud-monitors").replaceChildren(...monitors.flatMap((item) => row(item.name,
    item.up === null ? "checking" : item.up ? "up" : "down", item.up === false ? "bad" : item.up === null ? "off" : "",
    item.up === false ? item.reason || "Not answering" : "")));
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

function cameraLine(camera) {
  if (camera.offline) return ["Frigate gets no picture", false];
  if (!camera.last) return ["No events yet", null];
  const when = new Date(camera.last.start * 1000).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
  const what = camera.last.who || camera.last.label, where = camera.last.zones.length ? `, ${camera.last.zones.join(", ").replaceAll("_", " ")}` : "";
  return [`${what}${where}, ${when}`, true];
}

function showCameras(view) {
  $("frigate-url").value = view.url;
  $("frigate-user").value = view.user;
  $("frigate-password").value = "";
  $("frigate-password").placeholder = view.user ? "Saved; leave empty to keep it" : "";
  $("frigate-off").hidden = !view.url;
  $("frigate-state").textContent = !view.url ? "Not connected" : view.connected ? "Connected" : "Not answering";
  $("frigate-state").className = !view.url ? "note" : view.connected ? "good" : "bad";
  if (view.reason) say("frigate-message", view.reason);
  if (view.model_problem) say("camera-message", view.model_problem, "bad");
  $("camera-card").hidden = !view.cameras.length;
  $("camera-home-box").hidden = world.houses.length < 2;
  $("camera-home").replaceChildren(...[{ id: "", name: "Choose..." }, ...world.houses].map((house) => {
    const option = element("option", house.name);
    option.value = house.id;
    option.selected = house.id === (view.house || "");
    return option;
  }));
  $("camera-list").replaceChildren(...view.cameras.map((camera) => {
    const row = element("li"), left = element("span", cameraName(camera.name)), box = element("label", undefined, "check");
    const input = element("input");
    input.type = "checkbox";
    input.checked = camera.on;
    input.addEventListener("change", () => busy(input, "camera-message", async () => {
      showCameras(await api("camera", { camera: camera.name, on: input.checked }));
      return input.checked ? "Watching" : "Not watching. Its events and picture were dropped.";
    }));
    if (camera.on) left.append(element("span", cameraLine(camera)[0], "note sub"));
    if (camera.last?.description) left.append(element("span", camera.last.description, "note sub"));
    box.append(input, " Watch");
    const side = element("span");
    side.append(box);
    if (camera.on) {
      const scene = element("details", undefined, "scene"), summary = element("summary", camera.scene ? "What it sees: written" : "Describe what it sees");
      const text = element("textarea"), save = element("button", "Save"), look = element("img");
      text.value = camera.scene;
      text.maxLength = 600;
      text.rows = 4;
      text.placeholder = "Things BRAM can spot in any picture, wherever it points. Ours: the concrete driveway with the basketball hoop. Neighbors': the house with the red door and its driveway. The street: people walking there don't matter.";
      text.setAttribute("aria-label", `What ${cameraName(camera.name)} sees`);
      look.alt = `${cameraName(camera.name)} now`;
      scene.addEventListener("toggle", () => {
        if (scene.open) look.src = `/api/camera-live?camera=${encodeURIComponent(camera.name)}&t=${Date.now()}`;
      });
      save.type = "button";
      save.addEventListener("click", () => busy(save, "camera-message", async () => {
        showCameras(await api("camera-scene", { camera: camera.name, text: text.value }));
        return "Saved. Your model gets it with each picture from this camera.";
      }));
      scene.append(summary, look, text, save);
      left.append(scene);
      const words = element("label", undefined, "check"), say = element("input");
      say.type = "checkbox";
      say.checked = camera.describe;
      say.addEventListener("change", () => busy(say, "camera-message", async () => {
        const confirm = await askPassword(say.checked ? `Pictures from ${cameraName(camera.name)} will go to your own model to be described.` : `Stop describing ${cameraName(camera.name)}?`);
        showCameras(await api("camera-describe", { camera: camera.name, on: say.checked, confirm }));
        return say.checked ? "Your model describes this camera's events" : "Not described";
      }));
      words.append(say, " Describe");
      side.append(words);
    }
    row.append(left, side);
    return row;
  }));
  const on = view.cameras.filter((camera) => camera.on);
  // What BRAM was taught, newest first, each with Forget.
  $("learned-card").hidden = !view.learned.length;
  $("learned-list").replaceChildren(...view.learned.map((item, index) => ({ item, index })).reverse().map(({ item, index }) => {
    const row = element("li"), left = element("span", `${cameraName(item.camera)}: ${item.label}, ${item.matters ? "matters" : "doesn't matter"}`);
    if (item.note) left.append(element("span", item.note, "note sub"));
    if (item.seen) left.append(element("span", `It saw: ${item.seen}`, "note sub"));
    const forget = element("button", "Forget", "quiet small");
    forget.addEventListener("click", () => busy(forget, "learned-message", async () => {
      showCameras(await api("camera-forget", { index }));
      return "Forgotten";
    }));
    row.append(left, forget);
    return row;
  }));
  $("quiet-card").hidden = !view.quiet.length;
  $("quiet-list").replaceChildren(...view.quiet.map((item, index) => {
    const row = element("li"), left = element("span", `${cameraName(item.camera)}: ${item.label}${item.zones.length ? ` in ${item.zones.join(", ")}` : " outside every zone"}`);
    if (item.note) left.append(element("span", item.note, "note sub"));
    const allow = element("button", "Tell me again", "quiet small");
    allow.addEventListener("click", () => busy(allow, "quiet-message", async () => {
      showCameras(await api("camera-allow", { index }));
      return "BRAM tells you about these again";
    }));
    row.append(left, allow);
    return row;
  }));
  showLooking(view, on);
  $("home-cameras-card").hidden = !on.length;
  dots("home-cameras", on.map((camera) => {
    const [text, good] = cameraLine(camera);
    return [cameraName(camera.name), good, text];
  }));
}

// Does it matter? The answer, and what it was, teach BRAM's model about this camera.
function notNews(camera, event, key) {
  const acts = element("div", undefined, "acts"), ask = element("small", "Does it matter?");
  const yes = element("button", "It matters"), no = element("button", "Doesn't matter"), link = element("a", "Cameras");
  link.href = "#cameras";
  const answer = (matters) => {
    const form = element("form", undefined, "acts"), note = element("input"), save = element("button", "Tell BRAM");
    note.placeholder = matters ? "What is it? Such as a delivery at our door" : "What is it? Such as the neighbor in his driveway";
    note.maxLength = 200;
    note.setAttribute("aria-label", "What is it");
    form.addEventListener("submit", async (submitted) => {
      submitted.preventDefault();
      save.disabled = true;
      try {
        showCameras(await api("camera-learn", { camera: camera.name, id: event.id, matters, note: note.value }));
        closePop(key);
      } catch (error) {
        save.disabled = false;
        save.textContent = error.message;
      }
    });
    form.append(note, save);
    acts.replaceWith(form);
    note.focus();
  };
  for (const [button, matters] of [[yes, true], [no, false]]) {
    button.type = "button";
    button.addEventListener("click", () => answer(matters));
  }
  acts.append(ask, yes, no, link);
  return acts;
}

// Camera names as people say them: RoofCamera is Roof camera.
function cameraName(name) {
  const words = name.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const PEOPLE_AND_THINGS = { person: "Person", car: "Car", package: "Package", dog: "Dog", cat: "Cat" };

function showLooking(view, on) {
  const pretty = cameraName;
  const latest = on.filter((camera) => camera.last).sort((a, b) => b.last.start - a.last.start)[0];
  $("look-quiet").hidden = Boolean(on.length);
  $("look-count").textContent = on.length ? `${on.length} camera${on.length === 1 ? "" : "s"}` : "Nothing";
  $("look-shot").hidden = !latest?.shot;
  if (latest?.shot) {
    const src = `/api/camera-picture?camera=${encodeURIComponent(latest.name)}&e=${encodeURIComponent(latest.last.id)}`;
    if ($("look-img").getAttribute("src") !== src) $("look-img").src = src;
    $("look-img").alt = `${pretty(latest.name)}: ${cameraLine(latest)[0]}`;
    $("look-caption").textContent = `${pretty(latest.name)} · ${cameraLine(latest)[0]}${latest.last.quiet ? ` · ${latest.last.quiet}` : latest.last.description ? ` · ${latest.last.description}` : ""}`;
  }
  $("hud-cameras").replaceChildren(...on.flatMap((camera) => {
    const [text, good] = cameraLine(camera);
    return row(pretty(camera.name), camera.offline ? "no picture" : camera.last ? camera.last.who || camera.last.label : "quiet", good === false ? "bad" : good ? "" : "off", camera.last ? text : "");
  }));
  // Words from the model come later; they fill in a window that is still open.
  for (const camera of on) {
    const words = camera.last?.description, win = words && $("hud-alerts").querySelector(`[data-key="${CSS.escape(`camera:${camera.last.id}`)}"] .body`);
    if (win && !win.querySelector(".words")) win.insertBefore(element("p", words, "words"), win.querySelector("small")?.nextSibling || null);
  }
  // An event BRAM told you about pops up over the brain with its picture. Everything else
  // only updates Looking at. The first look only learns what is there.
  for (const camera of on) {
    const event = camera.last, key = event && `camera:${event.id}`;
    if (!event || seen.cameras.has(key) || !(event.told || !seen.camerasReady)) continue;
    const first = !seen.camerasReady;
    seen.cameras.add(key);
    if (first || Date.now() / 1000 - event.start > 300) continue;
    const what = event.who || PEOPLE_AND_THINGS[event.label] || event.label;
    for (const win of [...$("hud-alerts").querySelectorAll('[data-key^="camera:"]')]) win.remove();
    popUp(key, event.label === "person" ? "warn" : "good", `Camera · ${pretty(camera.name)}`, `${what} at ${pretty(camera.name)}`,
      [event.zones.join(", ").replaceAll("_", " "), new Date(event.start * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })].filter(Boolean).join(" · "),
      null,
      camera.shot ? `/api/camera-picture?camera=${encodeURIComponent(camera.name)}&e=${encodeURIComponent(event.id)}` : "",
      notNews(camera, event, key));
  }
  seen.camerasReady = true;
}

// Memory: everything shown here can be changed or deleted (E7).
function showMemory(view) {
  world.memoryOn = view.on;
  $("memory-state").textContent = view.on ? "On" : "Off";
  $("memory-state").className = view.on ? "good" : "note";
  $("memory-toggle").textContent = view.on ? "Turn off" : "Turn on";
  $("memory-forget").hidden = !view.items.length;
  $("memory-card").hidden = !view.on && !view.items.length;
  $("memory-list").replaceChildren(...(view.items.length ? view.items.map((item) => {
    const row = element("li"), left = element("span", item.text);
    left.append(element("span", `${item.person} · ${item.source} · ${new Date(item.at * 1000).toLocaleDateString()}`, "note sub"));
    const side = element("span"), change = element("button", "Change", "quiet small"), remove = element("button", "Delete", "quiet small");
    change.addEventListener("click", () => {
      const form = element("form", undefined, "row"), input = element("input"), save = element("button", "Save", "small");
      input.value = item.text;
      input.maxLength = 300;
      input.setAttribute("aria-label", "What to remember");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        busy(save, "memory-list-message", async () => {
          showMemory(await api("memory-edit", { id: item.id, text: input.value }));
          return "Changed";
        });
      });
      form.append(input, save);
      row.replaceChildren(form);
      input.focus();
    });
    remove.addEventListener("click", () => busy(remove, "memory-list-message", async () => {
      showMemory(await api("memory-delete", { id: item.id }));
      return "Deleted";
    }));
    side.append(change, remove);
    row.append(left, side);
    return row;
  }) : [element("li", view.on ? "Nothing yet. Say \"Remember that...\" in chat." : "Nothing.")]));
}

async function loadMemory() {
  showMemory(await api("memory"));
}

function showRouter(view) {
  world.router = view;
  $("router-url").value = view.url;
  $("router-secret").value = "";
  $("router-secret").placeholder = view.url ? "Saved; leave empty to keep it" : "";
  $("router-off").hidden = !view.url;
  $("router-state").textContent = !view.url ? "Not connected" : view.connected ? `Connected${view.version ? ` · OPNsense ${view.version}` : ""}${view.update ? " · update waiting" : ""}` : "Not answering";
  $("router-state").className = !view.url ? "note" : view.connected ? "good" : "bad";
  if (view.reason) say("router-message", view.reason, "bad");
  $("router-card").hidden = !view.devices;
  $("router-count").textContent = `${view.devices} device${view.devices === 1 ? "" : "s"} on your networks`;
  let where = null;
  $("router-list").replaceChildren(...view.list.flatMap((item) => {
    const rows = [];
    if (item.where !== where) {
      where = item.where;
      rows.push(element("li", where || "Network", "note"));
    }
    const row = element("li"), left = element("span", item.name || "No name");
    left.append(element("span", `${item.ip} · ${item.mac}`, "note sub"));
    row.append(left);
    rows.push(row);
    return rows;
  }));
}

async function loadRouter() {
  showRouter(await api("router"));
}

async function loadCameras() {
  world.cameraView = await api("cameras");
  showCameras(world.cameraView);
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
    $("detail").textContent = "See Needs you. Home Assistant has messaged your phones if you set that up.";
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
  deck.listen(null);
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
  // BRAM's core moves with its own voice.
  const ear = player.createAnalyser();
  ear.fftSize = 256;
  playing.connect(ear);
  ear.connect(player.destination);
  deck.listen(ear, "speaking");
  const mine = playing;
  playing.addEventListener("ended", () => { if (playing === mine || !playing) deck.listen(null); });
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
    deck.listen(null);
    for (const track of stream.getTracks()) track.stop();
    await context.close();
    return toPcm(parts, context.sampleRate);
  };
  try {
    await context.audioWorklet.addModule("recorder.js");
    const node = new AudioWorkletNode(context, "recorder");
    node.port.onmessage = (event) => parts.push(event.data);
    const input = context.createMediaStreamSource(stream), ear = context.createAnalyser();
    ear.fftSize = 256;
    input.connect(node);
    input.connect(ear);
    deck.listen(ear, "listening");
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
  climate: "Climate", temperature: "Climate", humidity: "Climate", appliance: "Appliances", valve: "Appliances", other: "Other",
};
const ORDER = ["Safety", "Locks and doors", "People", "Motion", "Climate", "Lights", "Switches and fans", "Media", "Voice", "Appliances", "Other"];

function arrange() {
  deck.update(world.groups.filter((group) => group.title !== "People"));
  // Readings the brain points out in turn, such as LIVING ROOM 74°.
  const readings = (world.devicesNow || []).filter((d) => ["temperature", "humidity"].includes(d.kind) && typeof d.values?.now === "number")
    .map((d) => ({ label: d.area || d.name, value: d.kind === "humidity" ? `${Math.round(d.values.now)}%` : `${Math.round(d.values.now)}°` }));
  deck.points(readings);
}

const PRINTER = { printing: "Printing", paused: "Paused", finished: "Finished", failed: "Failed", stopped: "Stopped", idle: "Idle", off: "Off", unknown: "Unknown", failing: "Integration failing" };
const RUNNING = ["cooling", "heating", "fan", "drying"];
const SAFETY = new Set(["leak", "smoke", "co", "gas", "heat", "hazard"]);

// A row on one of the side screens: what, a value, and why underneath.
function row(text, value, kind = "", why = "", tip = false) {
  const line = element("div", undefined, `row ${kind}`);
  line.append(element("span", text), element("b", value));
  line.title = text;
  const out = [line];
  if (why) out.push(element("span", why, tip ? "why tip" : "why"));
  return out;
}

function bar(share, kind = "") {
  const box = element("div", undefined, `bar ${kind}`), fill = element("i");
  fill.style.width = `${Math.round(Math.max(0, Math.min(1, share)) * 100)}%`;
  box.append(fill);
  return box;
}

function meterRow(word, share, text) {
  const line = element("div", undefined, "meter"), track = element("i"), fill = element("em");
  fill.style.width = `${Math.round(Math.max(0, Math.min(1, share)) * 100)}%`;
  track.append(fill);
  line.append(element("span", word), track, element("b", text));
  return line;
}

// Which of the systems around the brain a device belongs to.
function systemOf(device) {
  if (SAFETY.has(device.kind)) return "Safety";
  if (device.kind === "person") return "People";
  if (device.kind === "lock" || device.kind === "opening") return "Security";
  if (device.kind === "climate") return "Climate";
  if (device.kind === "light") return "Lights";
  if (device.kind === "motion") return "House";
  return "";
}

async function loadHouse() {
  const { homes, alerts, printers, rooms: occupancy } = await api("house");
  world.rooms = new Map(occupancy.map((room) => [room.room, room]));
  const groups = new Map(), urgent = [];
  let total = 0, unseen = 0;
  for (const home of homes) {
    for (const device of home.devices) {
      total += 1;
      if (device.state === "unknown") unseen += 1;
      if (device.state === "alert") urgent.push(device);
      const title = TITLES[device.kind] || "Other";
      if (!groups.has(title)) groups.set(title, []);
      const photo = device.picture ? `/api/picture?${new URLSearchParams({ home: home.id, id: device.id, v: device.picture })}` : "";
      groups.get(title).push({ ...device, photo, age: device.since && device.state !== "unknown" ? ago(device.since) : "" });
    }
  }
  const devices = [...groups.values()].flat();
  world.devicesNow = devices;
  world.printersNow = printers;
  world.alertsNow = alerts;
  world.urgentNow = urgent;
  world.seen = [total - unseen, total];
  happenings(devices);
  world.groups = ORDER.filter((title) => groups.has(title)).map((title) => ({ title, devices: groups.get(title) }));
  arrange();
  world.devices = total;
  world.urgent = urgent.length;
  // The alert list for the classic look
  const rows = [...urgent.map((d) => [`${d.name}: ${d.says}`, "now", true]),
    ...alerts.map((alert) => [alert.text, ago(alert.created), Boolean(alert.safety)])];
  $("alert-count").textContent = rows.length ? String(rows.length) : "";
  $("alerts-panel").classList.toggle("red", rows.some(([, , bad]) => bad));
  $("open-alerts").replaceChildren(...(rows.length ? rows.map(([text, when, bad]) => {
    const line = element("li", undefined, bad ? "bad" : "");
    line.append(element("span", text), element("span", when, "note"));
    return line;
  }) : [element("li", "Nothing needs you", "note")]));
  showHouse(devices);
  showPrinters(printers);
}

// The house: each room from Home Assistant's areas, lit where someone moves, amber where something is open.
function showHouse(devices) {
  const areas = new Map();
  for (const d of devices) {
    if (!d.area) continue;
    const room = areas.get(d.area) || { name: d.area, lit: false, open: false, people: [] };
    if (d.kind === "opening" && d.state === "warn") room.open = true;
    areas.set(d.area, room);
  }
  for (const [name, seen] of world.rooms) {
    const room = areas.get(name) || { name, lit: false, open: false, people: [] };
    room.lit = seen.state === "occupied";
    room.people = seen.people;
    areas.set(name, room);
  }
  const rooms = [...areas.values()].sort((a, b) => a.name.localeCompare(b.name));
  $("house-pane").hidden = !rooms.length;
  deck.house(rooms);
  const people = devices.filter((d) => d.kind === "person"), home = people.filter((d) => d.state === "on");
  const open = devices.filter((d) => d.kind === "opening" && d.state === "warn").length;
  $("house-count").textContent = [people.length && `${home.length} home`, `${open} open`].filter(Boolean).join(" · ");
}

function setLook(look) {
  const command = look !== "classic";
  document.body.classList.toggle("command", command);
  // One chat and one alert list, moved to where the look wants them.
  if (command) {
    $("slot-chat").append($("chat-form"), $("aloud-box"));
    $("slot-message").append($("chat-message"));
    $("slot-start").append($("start"));
  } else {
    $("chat-log").after($("chat-form"), $("aloud-box"), $("chat-message"));
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
  const now = new Date();
  $("clock").textContent = now.toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  $("day-name").textContent = now.toLocaleDateString([], { weekday: "long" });
  $("day-num").textContent = String(now.getDate());
  $("day-month").textContent = now.toLocaleDateString([], { month: "short" });
  $("time-now").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  $("time-sec").textContent = `:${String(now.getSeconds()).padStart(2, "0")}`;
  // Countdowns move every second, between visits to the server.
  for (const node of document.querySelectorAll("[data-due]")) node.textContent = countdown(Number(node.dataset.due) - Date.now() / 1000);
}

function countdown(seconds) {
  if (seconds <= 0) return "now";
  const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = Math.floor(seconds % 60);
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

function days() {
  const today = new Date(), list = [];
  for (let d = -10; d <= 10; d += 1) {
    const day = new Date(today);
    day.setDate(today.getDate() + d);
    list.push(element("span", String(day.getDate()).padStart(2, "0"), d === 0 ? "today" : ""));
  }
  $("hud-days").replaceChildren(...list);
}

// --- what BRAM is doing ---

const seen = { states: null, decisions: new Set(), watching: new Set(), said: "", cameras: new Set(), camerasReady: false, needs: null, spot: 0 };

// Alerts open as windows over the brain. Red ones stay until closed; others close by themselves.
function popUp(key, kind, title, text, detail = "", link = null, picture = "", acts = null) {
  const box = $("hud-alerts");
  if (!box || $("deck").hidden || box.querySelector(`[data-key="${CSS.escape(key)}"]`)) return;
  while (box.children.length >= 3) box.firstChild.remove();
  const win = element("section", undefined, `window ${kind}`), frame = element("div", undefined, "frame"), bar = element("div", undefined, "bar"), body = element("div", undefined, "body");
  win.dataset.key = key;
  win.setAttribute("role", kind === "bad" ? "alert" : "status");
  const close = element("button", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Close");
  close.addEventListener("click", () => closePop(key));
  const label = element("span", title);
  label.title = "Open";
  label.addEventListener("click", () => unfold(win));
  bar.append(label, element("small", new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })), close);
  if (picture) {
    const shot = element("div", undefined, "shot"), img = element("img");
    img.src = picture;
    img.alt = text;
    img.addEventListener("error", () => shot.remove());  // no picture yet: just the words
    shot.append(img);
    body.append(shot);
  }
  body.append(element("b", text));
  if (detail) body.append(element("small", detail));
  const row = acts || element("div", undefined, "acts");
  if (link) {
    const a = element("a", link.label);
    a.href = link.href;
    a.addEventListener("click", () => closePop(key));
    row.append(a);
  }
  if (row.children.length) body.append(row);
  frame.append(element("i", undefined, "ticks"), bar, body);
  win.append(frame, element("i", undefined, "wire"));
  box.append(win);
  unfold(win);
  deck.pulse("", kind === "bad" ? "bad" : kind === "warn" ? "warn" : "main");
  if (kind !== "bad") setTimeout(() => closePop(key), kind === "warn" ? 30000 : 15000);
}

// One window open at a time; the others fold to their title bar.
function unfold(win) {
  for (const other of $("hud-alerts").children) other.classList.toggle("folded", other !== win);
}

function closePop(key) {
  const win = $("hud-alerts")?.querySelector(`[data-key="${CSS.escape(key)}"]`);
  if (!win || win.classList.contains("going")) return;
  win.classList.add("going");
  setTimeout(() => win.remove(), 800);
}
const DID = { sent: "Told your phone", "not sent": "Could not send", held: "Held back", acked: "Acknowledged", stopped: "You stopped", snoozed: "Snoozed" };

const SPOTS = [[34, 17], [66, 17], [34, 61], [66, 61]];

// Something happened: a card comes, stays a moment, and goes, and a pulse runs from that system into the brain.
function happen(text, kind = "", detail = "", system = "") {
  const box = $("hud-events");
  if (!box || $("deck").hidden) return;
  while (box.children.length >= 4) box.firstChild.remove();
  // Four places around the brain, taken in turn, so cards never land on each other.
  const card = element("div", undefined, `event ${kind}`), [x, y] = SPOTS[seen.spot++ % SPOTS.length];
  for (const other of box.children) if (other.dataset.spot === `${x},${y}`) other.remove();
  card.dataset.spot = `${x},${y}`;
  card.style.setProperty("--x", `${x}%`);
  card.style.setProperty("--y", `${y}%`);
  const frame = element("div", undefined, "frame");
  frame.append(element("small", detail || "BRAM"), element("b", text));
  card.append(frame);
  box.append(card);
  deck.pulse(system, kind === "bad" ? "bad" : kind === "warn" ? "warn" : "main");
  setTimeout(() => card.classList.add("going"), 9000);
  setTimeout(() => card.remove(), 10500);
}

// The room is on the card's tab, so the words do not say it again: under MASTER BEDROOM,
// "Master Bedroom motion: motion detected" is "Motion detected", and a bed lamp is "Bed lamp: on".
function cardText(device) {
  const area = (device.area || "").toLowerCase();
  let rest = device.name;
  if (area && rest.toLowerCase().startsWith(area)) rest = rest.slice(area.length).trim();
  const says = device.says || "";
  const text = !rest || says.toLowerCase().includes(rest.toLowerCase()) ? says : `${rest}: ${says}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function happenings(devices) {
  const now = new Map(devices.map((d) => [d.id, d]));
  if (seen.states) {
    for (const [id, device] of now) {
      const before = seen.states.get(id);
      if (!before || before.says === device.says || device.state === "unknown" || before.state === "unknown") continue;
      // Readings drift all day; those are for the charts, not for cards. Motion ending is
      // not news either: only motion starting gets a card.
      if (["temperature", "humidity", "other"].includes(device.kind)) continue;
      if (device.kind === "motion" && /^(no motion|clear|not detected|no presence)/i.test(device.says)) continue;
      const kind = device.state === "alert" ? "bad" : device.state === "warn" ? "warn" : "";
      happen(cardText(device), kind, device.area || "", systemOf(device));
    }
  }
  seen.states = new Map([...now].map(([id, d]) => [id, { says: d.says, state: d.state }]));
}

const WHY = { rule: "I tell you when the time is up.", night: "From then I check every lock.", problem: "It is a problem if it lasts." };

function showWatching(brain) {
  const printers = world.printersNow || [];
  $("watch-count").textContent = brain.watching.length ? String(brain.watching.length) : "";
  $("hud-watch").replaceChildren(...(brain.watching.length ? brain.watching.flatMap((item) => {
    const key = `${item.kind}:${item.text}`, fresh = seen.watching.size && !seen.watching.has(key);
    const [line] = row(item.text, item.told ? "told" : item.due ? countdown(item.due - brain.now) : "", `${item.kind === "rule" && !item.told ? "warn" : ""}${fresh ? " new" : ""}`);
    if (item.due && !item.told) line.lastChild.dataset.due = String(item.due);
    const out = [line];
    if (item.due && item.since) out.push(bar((brain.now - item.since) / Math.max(1, item.due - item.since), item.kind === "printer" ? "printer" : ""));
    let why = item.told ? "I told you. Watching until it ends." : WHY[item.kind] || "";
    if (item.kind === "printer") {
      const p = printers.find((x) => item.text.startsWith(`${x.name}:`));
      const heat = p && "nozzle" in p ? `Nozzle ${p.nozzle}${p.nozzle_target ? `/${p.nozzle_target}` : ""}${p.unit || ""}` : "";
      why = [p && "progress" in p && `${p.progress}% done`, heat, "I tell you when it finishes"].filter(Boolean).join(" · ") + ".";
    }
    out.push(element("span", why, "why"));
    return out;
  }) : [element("p", "Nothing counting down. All quiet.", "quiet")]));
  for (const item of brain.watching) {
    const key = `${item.kind}:${item.text}`;
    if (seen.watching.size && !seen.watching.has(key)) happen(`Watching: ${item.text}`, "", item.due ? `due in ${countdown(item.due - brain.now)}` : "", item.kind === "printer" ? "Printers" : "Security");
    seen.watching.add(key);
  }
}

function showDid(brain) {
  const first = !seen.decisions.size;
  $("did-count").textContent = brain.sent_today ? `${brain.sent_today} sent today` : "Today";
  $("hud-did").replaceChildren(...(brain.decisions.length ? brain.decisions.flatMap((d) => {
    const fresh = !first && !seen.decisions.has(`${d.at}:${d.what}`);
    const when = new Date(d.at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    return row(`${DID[d.what] || d.what}: ${d.about}`, when, `${d.what === "held" || d.what === "not sent" ? "warn" : ""}${fresh ? " new" : ""}`,
      d.what === "held" || d.what === "not sent" ? d.text : "");
  }) : [element("p", "Nothing to tell you yet today.", "quiet")]));
  for (const d of brain.decisions) {
    const key = `${d.at}:${d.what}`;
    if (!first && !seen.decisions.has(key)) happen(DID[d.what] || d.what, d.what === "held" ? "warn" : "", d.about, "Messages");
    seen.decisions.add(key);
  }
}

// What you can do about a finding from Home: read its story, or hide it from the list.
function needActs(need) {
  const box = element("div", undefined, "acts"), story = element("a", "Story"), hide = element("button", "Hide");
  story.href = need.key ? `#finding=${encodeURIComponent(need.key)}` : "#findings";
  hide.type = "button";
  hide.title = "Off this list until it happens again. It does not change what is sent to your phone.";
  hide.addEventListener("click", async () => {
    hide.disabled = true;
    try {
      await api("finding-ignore", { id: need.id, on: true });
      await loadBrain();
    } catch (error) {
      hide.disabled = false;
      hide.textContent = error.message;
    }
  });
  box.append(story, ...pressButtons(need, loadBrain), hide);
  return box;
}

// The same Stop these and Less often the phone was given. Home Assistant checks each press.
const PRESS_TIP = { "Stop these": "No more messages like this. Undo in Home Assistant with the BRAM button Allow stopped messages.", "Less often": "At most once a day from now on." };
function pressButtons(item, reload) {
  return (item.buttons || []).map((offered) => {
    const button = element("button", offered.title, "quiet small");
    button.type = "button";
    button.title = PRESS_TIP[offered.title] || "";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await api("press", { id: item.id, action: offered.action });
        await reload();
      } catch (error) {
        button.disabled = false;
        button.textContent = error.message;
      }
    });
    return button;
  });
}

// Printers only while they print, or when one has a problem.
function showPrinters(list) {
  const shown = list.filter((p) => ["printing", "paused"].includes(p.state));
  $("printers-pane").hidden = !shown.length;
  $("printers-count").textContent = shown.length > 1 ? String(shown.length) : "";
  $("hud-printers").replaceChildren(...shown.map((p) => {
    const box = element("div", undefined, `printer ${p.problem ? "problem" : p.state}`);
    const head = element("div", undefined, "row");
    head.append(element("span", p.name || "Printer"), element("em", PRINTER[p.state] || p.state));
    box.append(head);
    if ("progress" in p) {
      box.append(...row(p.file || "Print", `${p.progress}%`, "", "left" in p ? `${lasted(p.left)} left` : ""));
      box.append(bar(p.progress / 100, "printer"));
    } else if (p.file) {
      box.append(element("span", p.file, "why"));
    }
    for (const [key, word] of [["nozzle", "Nozzle"], ["nozzle2", "Left nozzle"], ["bed", "Bed"], ["chamber", "Chamber"]]) {
      if (!(key in p)) continue;
      const target = p[`${key}_target`];
      box.append(meterRow(word, target ? p[key] / target : Math.min(1, p[key] / 300), `${p[key]}${target ? `/${target}` : ""}${p.unit || ""}`));
    }
    if (p.problem) box.append(element("span", p.problem_text ? `Problem: ${p.problem_text}` : "It reports a problem.", "why tip"));
    if (p.state === "failing") box.append(element("span", "Its integration cannot start in Home Assistant.", "why tip"));
    return box;
  }));
}

function showNeeds(brain) {
  const rows = [
    ...(world.urgentNow || []).map((d) => row(`${d.name}: ${d.says}`, "now", "bad", d.area ? `In ${d.area}. Home Assistant has messaged your phones if you set that up.` : "", true)),
    ...(world.alertsNow || []).map((a) => row(a.text, ago(a.created), a.safety ? "bad" : "warn")),
    ...brain.needs.map((n) => [...row(n.text, n.times > 1 ? `${n.times} times` : ago(n.first), n.severity === "high" ? "bad" : "warn",
      `${n.times === 1 ? "Since" : "First"} ${ago(n.first)}${n.told ? ". I told you" : ""}.`, true), needActs(n)]),
  ];
  $("needs-pane").hidden = !rows.length;
  const urgent = world.urgentNow || [], alerts = world.alertsNow || [];
  const keys = new Map([
    ...urgent.map((d) => [`urgent:${d.id}`, ["bad", d.area ? `${d.area} · alert` : "Alert", `${d.name}: ${d.says}`, "Home Assistant has messaged your phones if you set that up.", null]]),
    ...alerts.map((a) => [`alert:${a.text}`, [a.safety ? "bad" : "warn", a.safety ? "Safety" : "Needs you", a.text, ago(a.created), null]]),
    ...brain.needs.map((n) => [`need:${n.id}`, [n.severity === "high" ? "bad" : "warn", FROM[n.source] || "Needs you", n.text, n.told ? "I told your phone." : "", needActs(n)]]),
  ]);
  if (seen.needs) {
    for (const [key, [kind, title, text, detail, acts]] of keys) {
      if (!seen.needs.has(key)) popUp(key, kind, title, text, detail, null, "", acts);
    }
    for (const key of seen.needs) if (!keys.has(key)) closePop(key);
  }
  seen.needs = new Set(keys.keys());
  const down = (world.monitors || []).some((m) => m.up === false);
  const lost = world.houses.some((h) => !h.connected);
  deck.alert(lost || urgent.length || alerts.some((a) => a.safety) || brain.needs.some((n) => n.severity === "high") ? "bad"
    : alerts.length || brain.needs.length || down ? "warn" : "");
  $("needs-count").textContent = String((world.urgentNow || []).length + (world.alertsNow || []).length + brain.needs.length);
  $("hud-needs").replaceChildren(...rows.flat());
}

function showNoticed(brain) {
  const notes = [];
  for (const c of brain.compare || []) {
    if (Math.abs(c.apart) < 1.5) continue;
    notes.push(["Climate", `In ${c.area}, ${c.sensor} reads ${Math.abs(c.apart)}${c.unit} ${c.apart > 0 ? "warmer" : "cooler"} than ${c.climate} on average this week.`]);
  }
  if (brain.nights < 14) notes.push(["Nights", `${brain.nights} of 14 nights learned. Then I know when the house goes quiet.`]);
  const [seenNow, total] = world.seen || [0, 0];
  if (total && total - seenNow) notes.push(["Sensors", `${total - seenNow} of ${total} things are not reporting a state right now.`]);
  $("noticed-pane").hidden = !notes.length;
  $("hud-noticed").replaceChildren(...notes.slice(0, 4).map(([what, text]) => {
    const line = element("span", undefined, "why");
    line.append(element("b", what), ` ${text}`);
    return line;
  }));
}

function showClimate(brain) {
  const inside = brain.series.map((s) => s.inside), outside = brain.series.map((s) => s.outside);
  const known = [...inside, ...outside].filter((v) => v !== null);
  $("climate-pane").hidden = brain.history && !known.length && !brain.climate.length;
  $("climate-start").hidden = brain.history;
  if ($("climate-pane").hidden) return;
  const last = (list) => [...list].reverse().find((v) => v !== null && v !== undefined);
  const out = last(outside), inn = last(inside);
  deck.weather(out ?? null);
  $("temp-out").textContent = out === undefined ? "--" : `${Math.round(out)}°`;
  $("climate-now").textContent = [out !== undefined && `${out}° out`, inn !== undefined && `${inn}° in`].filter(Boolean).join(" · ");
  const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 300 46");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("preserveAspectRatio", "none");
  const low = Math.min(...known) - 1, high = Math.max(...known) + 1;
  for (const [values, kind] of [[outside, "outside"], [inside, "inside"]]) {
    const points = values.map((v, i) => v === null ? null : `${(i / Math.max(1, values.length - 1)) * 300},${46 - ((v - low) / (high - low || 1)) * 42 - 2}`).filter(Boolean);
    if (points.length < 2) continue;
    const path = document.createElementNS(NS, "polyline");
    path.setAttribute("points", points.join(" "));
    path.setAttribute("class", kind);
    svg.append(path);
  }
  const running = (world.devicesNow || []).filter((d) => d.kind === "climate" && RUNNING.includes(d.values?.action));
  const rows = brain.climate.slice(0, 4).flatMap((day) => {
    const ran = Object.values(day.seconds).reduce((x, y) => x + y, 0);
    const now = running.find((d) => d.name === day.name);
    return row(day.name, now ? `${now.values.action} · ${lasted(ran)}` : ran ? lasted(ran) : "idle", now ? "" : "off");
  });
  $("hud-climate").replaceChildren(...(known.length > 1 ? [svg] : []), ...rows);
  const total = brain.climate.reduce((sum, day) => sum + Object.values(day.seconds).reduce((x, y) => x + y, 0), 0);
  $("climate-why").textContent = known.length ? `Last 24 hours: inside solid, outside dashed.${total ? ` Ran ${lasted(total)} in all today.` : ""}${out === undefined ? " For outside, share a weather entity under What BRAM can see in Home Assistant." : ""}` : brain.history ? "Nothing recorded in the last 24 hours yet." : "History is off, so BRAM cannot show the day.";
}

// The system screen and the systems around the brain, from what is real.
function showSystems(brain) {
  const devices = world.devicesNow || [], printers = world.printersNow || [];
  const links = [...world.houses.map((house) => [house.name, house.connected]), ...world.monitors.map((item) => [item.name, item.up])];
  const up = links.filter(([, good]) => good).length;
  $("links-count").textContent = links.length ? `${up} of ${links.length} linked` : "";
  $("hud-systems").replaceChildren(...links.map(([name, good]) => {
    const tag = element("span");
    tag.append(element("i", undefined, good === null ? "dot checking" : good ? "dot" : "dot down"), name);
    return tag;
  }));
  const down = links.find(([, good]) => good === false);
  $("links-why").textContent = down ? `${down[0]} is not answering. What it tells me is paused until it does.` : brain.model ? `Thinking with ${brain.model}, on your own network.` : "Choose a brain under Settings.";
  const [seenNow, total] = world.seen || [0, 0];
  const shut = devices.filter((d) => d.kind === "lock" || d.kind === "opening"), secure = shut.filter((d) => d.state === "off").length;
  $("hud-meters").replaceChildren(
    meterRow("Seeing", total ? seenNow / total : 0, `${seenNow}/${total}`),
    ...(shut.length ? [meterRow("Secured", secure / shut.length, `${secure}/${shut.length}`)] : []),
    meterRow("Learned", brain.nights / 14, `${Math.min(brain.nights, 14)}/14`),
    meterRow("Told you", Math.min(1, brain.sent_today / 20), String(brain.sent_today)));
  const people = devices.filter((d) => d.kind === "person"), home = people.filter((d) => d.state === "on");
  const cool = devices.filter((d) => d.kind === "climate" && d.state !== "unknown"), busy = cool.filter((d) => RUNNING.includes(d.values?.action));
  const safety = devices.filter((d) => SAFETY.has(d.kind)), alarm = safety.filter((d) => d.state === "alert");
  const lights = devices.filter((d) => d.kind === "light"), lit = lights.filter((d) => d.state === "on");
  const open = shut.length - secure;
  const list = [];
  list.push({ name: "Home Assistant", value: world.houses.every((h) => h.connected) && world.houses.length ? "linked" : "not linked", hot: world.houses.every((h) => h.connected) ? "" : "bad" });
  if (people.length) list.push({ name: "People", value: `${home.length} of ${people.length} home`, hot: "" });
  if (shut.length) list.push({ name: "Security", value: open ? `${open} open` : "all shut", hot: open ? "warn" : "" });
  if (safety.length) list.push({ name: "Safety", value: alarm.length ? `${alarm.length} alarm` : "all clear", hot: alarm.length ? "bad" : "" });
  if (cool.length) list.push({ name: "Climate", value: `${busy.length} running`, hot: "" });
  if (lights.length) list.push({ name: "Lights", value: `${lit.length} on`, hot: "" });
  if (printers.length) {
    const printing = printers.filter((p) => p.state === "printing"), failing = printers.some((p) => p.state === "failing" || p.problem);
    list.push({ name: "Printers", value: printing.length ? `${printing[0].progress ?? "--"}%` : PRINTER[printers[0].state] || "idle", hot: failing ? "warn" : "" });
  }
  if (world.monitors.length) {
    const upNow = world.monitors.filter((m) => m.up).length, down = world.monitors.filter((m) => m.up === false);
    list.push({ name: "Monitors", value: down.length ? `${down[0].name} down` : `${upNow} of ${world.monitors.length} up`, hot: down.length ? "bad" : "" });
  }
  const router = world.router;
  if (router?.url) list.push({ name: "Router", value: router.connected ? `${router.devices} devices` : "not answering", hot: router.connected ? (router.update ? "warn" : "") : "bad" });
  const cams = (world.cameraView?.cameras || []).filter((c) => c.on);
  if (cams.length) {
    const blind = cams.filter((c) => c.offline);
    list.push({ name: "Cameras", value: blind.length ? `${cameraName(blind[0].name)}: no picture` : `${cams.length} watching`, hot: blind.length ? "warn" : "" });
  }
  list.push({ name: "Model", value: brain.model ? brain.model.split(":")[0].slice(0, 16) : "none", hot: brain.model ? "" : "warn" });
  list.push({ name: "Messages", value: `${brain.sent_today} today`, hot: "" });
  list.push({ name: "Learning", value: `${Math.min(brain.nights, 14)} of 14 nights`, hot: "" });
  deck.orbit(list);
}

async function loadBrain() {
  const brain = await api("brain");
  world.brain = brain;
  showWatching(brain);
  showDid(brain);
  showNeeds(brain);
  showClimate(brain);
  showNoticed(brain);
  showSystems(brain);
  showFocus();
}

async function loadHome() {
  let problem = "";
  try {
    await Promise.all([loadStatus(), loadMonitors(), loadSettings(), loadLatest(), loadHouse(), loadCameras(), loadRouter()]);
    await loadBrain();
  } catch (error) {
    problem = error.message;
  }
  headline(problem);
  // BRAM says it when it changes, not every few seconds.
  const offline = world.houses.filter((h) => !h.connected);
  const since = offline.length && seen.downSince?.[offline[0].id] ? ` since ${new Date(seen.downSince[offline[0].id]).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : "";
  const words = offline.length && !problem && !world.urgent
    ? `${offline.length === 1 && world.houses.length === 1 ? "Home Assistant" : offline.map((h) => h.name).join(", ")} isn't answering${since}. I can't see your home until it's back.`
    : `${$("headline").textContent}. ${problem || world.urgent ? $("detail").textContent : world.devices ? `Watching ${world.devices} things.` : "Nothing is shared yet. In Home Assistant: BRAM, Configure, Recommended setup."}`;
  if (words !== seen.said && !document.body.classList.contains("thinking")) {
    seen.said = words;
    $("thought-facts").textContent = "";
    deck.say(words);
  }
}

// --- a closer look: click a system on the orbit, or a screen, and its detail opens over the brain ---

let focused = "";
const STATE_KIND = { warn: "warn", alert: "bad", unknown: "off" };

function deviceRows(list, empty) {
  if (!list.length) return [element("p", empty, "quiet")];
  const order = { alert: 0, warn: 1, on: 2, off: 3, unknown: 4 };
  return [...list].sort((a, b) => (order[a.state] ?? 5) - (order[b.state] ?? 5) || a.name.localeCompare(b.name))
    .flatMap((d) => row(d.name, d.says || d.state, STATE_KIND[d.state] || "", [d.area, d.age && `for ${d.age}`].filter(Boolean).join(" · ")));
}

const FOCUS = {
  People: (devices) => ["Who is home, and where.", deviceRows(devices.filter((d) => d.kind === "person"), "No people shared.")],
  Security: (devices) => ["Every lock, door, and window shared with BRAM. Open and unlocked first.", deviceRows(devices.filter((d) => d.kind === "lock" || d.kind === "opening"), "No locks or doors shared.")],
  Safety: (devices) => ["Leak, smoke, CO, gas, and heat sensors. These alert straight from Home Assistant.", deviceRows(devices.filter((d) => SAFETY.has(d.kind)), "No safety sensors shared.")],
  Lights: (devices) => ["Lights that are on come first.", deviceRows(devices.filter((d) => d.kind === "light"), "No lights shared.")],
  House: (devices) => ["Each room and what is in it.", [...new Set(devices.map((d) => d.area).filter(Boolean))].sort().flatMap((area) => {
    const here = devices.filter((d) => d.area === area), seen = world.rooms.get(area);
    const head = element("h3", area);
    const busy = [seen?.state === "occupied" && "someone there", ...here.filter((d) => d.state === "warn" || d.state === "alert").map((d) => `${d.name} ${d.says}`)].filter(Boolean);
    return [head, element("span", busy.length ? busy.join(" · ") : `${here.length} things, all quiet`, "why"), ...deviceRows(here, "")];
  })],
  Climate: (devices) => {
    const brain = world.brain || { climate: [] };
    const units = devices.filter((d) => d.kind === "climate").flatMap((d) => {
      const v = d.values || {}, day = brain.climate.find((c) => c.name === d.name);
      const ran = day ? Object.entries(day.seconds).map(([what, t]) => `${what} ${lasted(t)}`).join(", ") : "";
      return row(d.name, v.action || d.says, RUNNING.includes(v.action) ? "" : "off",
        [d.area, v.now !== undefined && `${v.now}° now`, v.target !== undefined && `set ${v.target}°`, ran && `today: ${ran}`].filter(Boolean).join(" · "));
    });
    const rooms = deviceRows(devices.filter((d) => d.kind === "temperature" || d.kind === "humidity"), "No room sensors shared.");
    return ["Each thermostat, what it is doing, and how long it ran today. Then the rooms' own sensors.", [...units, element("h3", "Room sensors"), ...rooms]];
  },
  Printers: () => ["Every printer, printing or not.", (world.printersNow || []).length ? world.printersNow.flatMap((p) => {
    const out = row(p.name || "Printer", PRINTER[p.state] || p.state, p.state === "failing" || p.problem ? "warn" : ["printing", "paused"].includes(p.state) ? "" : "off",
      [p.area, p.file, "progress" in p && `${p.progress}%`, "left" in p && `${lasted(p.left)} left`, "nozzle" in p && `nozzle ${p.nozzle}${p.unit || ""}`, "bed" in p && `bed ${p.bed}${p.unit || ""}`].filter(Boolean).join(" · "));
    return out;
  }) : [element("p", "No printers found.", "quiet")]],
  "Home Assistant": (devices) => {
    const quiet = devices.filter((d) => d.state === "unknown");
    return [world.houses.map((h) => `${h.name}: ${h.connected ? "linked" : "not linked"}`).join(". ") + `. ${devices.length} things shared.`,
      [element("h3", "Not reporting"), ...deviceRows(quiet, "Everything shared is reporting.")]];
  },
  System: () => {
    const links = [...world.houses.map((h) => [h.name, h.connected]), ...world.monitors.map((m) => [m.name, m.up])];
    return ["Everything BRAM depends on, and whether it answers.", links.flatMap(([name, good]) => row(name, good === null ? "checking" : good ? "answering" : "not answering", good === false ? "bad" : ""))];
  },
  Messages: () => {
    const brain = world.brain || { decisions: [] };
    return [`${brain.sent_today || 0} sent today. Everything BRAM told you, held back, or was told to stop since yesterday, and why.`,
      brain.decisions.length ? brain.decisions.flatMap((d) => row(`${DID[d.what] || d.what}: ${d.about}`,
        new Date(d.at * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" }), d.what === "held" || d.what === "not sent" ? "warn" : "", d.text)) : [element("p", "Nothing yet.", "quiet")]];
  },
  Learning: () => {
    const nights = world.brain?.nights || 0;
    return [`${nights} of 14 nights learned. After 14, BRAM suggests your night hours from when the house really goes quiet. See Learning in Home Assistant.`, []];
  },
};

function showFocus() {
  if (!focused) return;
  const make = FOCUS[focused];
  if (!make) return closeFocus();
  const [why, body] = make(world.devicesNow || []);
  $("focus-title").textContent = focused;
  $("focus-why").textContent = why;
  $("focus-body").replaceChildren(...body);
}

function openFocus(name) {
  if (!FOCUS[name]) return;
  focused = name;
  $("focus").hidden = false;
  showFocus();
  $("focus-close").focus();
}

function closeFocus() {
  focused = "";
  $("focus").hidden = true;
}

$("focus-close").addEventListener("click", closeFocus);
addEventListener("keydown", (event) => { if (event.key === "Escape" && focused) closeFocus(); });
for (const pane of document.querySelectorAll("[data-focus]")) {
  pane.addEventListener("click", (event) => { if (!event.target.closest("a, button, h2")) openFocus(pane.dataset.focus); });
}
// Click a screen's tab to fold it down to just the tab. Remembered in this browser only.
const FOLDED = "bram-folded";
function foldedNames() {
  try { return JSON.parse(localStorage.getItem(FOLDED) || "[]"); } catch { return []; }
}
for (const tab of document.querySelectorAll("#hud .side .glass > h2")) {
  const pane = tab.parentElement, name = tab.firstChild.textContent.trim();
  const set = (folded) => { pane.classList.toggle("folded", folded); tab.setAttribute("aria-expanded", String(!folded)); };
  tab.tabIndex = 0;
  tab.setAttribute("role", "button");
  tab.title = "Fold or open";
  set(foldedNames().includes(name));
  const toggle = (event) => {
    event.stopPropagation();
    const folded = !pane.classList.contains("folded"), names = foldedNames().filter((n) => n !== name);
    set(folded);
    try { localStorage.setItem(FOLDED, JSON.stringify(folded ? [...names, name] : names)); } catch { /* not kept */ }
  };
  tab.addEventListener("click", toggle);
  tab.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(event); } });
}
$("scope").addEventListener("click", (event) => {
  const box = $("scope").getBoundingClientRect(), name = deck.at(event.clientX - box.left, event.clientY - box.top);
  if (name) openFocus(name);
});
$("scope").addEventListener("mousemove", (event) => {
  const box = $("scope").getBoundingClientRect();
  $("scope").style.cursor = deck.at(event.clientX - box.left, event.clientY - box.top) ? "pointer" : "";
});

setInterval(() => {
  const home = signedIn && !document.hidden && !$("deck").hidden;
  if (home) loadHome();
}, 5000);
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
  $("history-off").hidden = data.on;
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
  const nights = Math.max(0, ...data.homes.map((home) => home.nights)), waiting = data.homes.map((home) => home.suggestion).filter(Boolean);
  $("learning-card").hidden = !nights && !waiting.length;
  $("learning-state").textContent = waiting.length ? `Waiting for you: ${waiting.join(" ")}` : nights >= 14 ? `${nights} nights noted. Nothing worth changing yet.` : `${nights} of 14 nights noted before the first suggestion.`;
  const prints = data.homes.flatMap((home) => home.prints);
  $("prints-card").hidden = !prints.length;
  $("history-prints").replaceChildren(...prints.map((print) => cells([new Date(print.end * 1000).toLocaleString(), print.printer, print.file || "unknown",
    print.result + (print.result !== "finished" && print.progress !== null ? ` at ${print.progress}%` : ""), print.whole ? lasted(print.end - print.start) : "not all seen",
    print.weight !== null ? `${print.weight} g` : ""])));
  if (!days.length) $("history-days").append(cells(["Nothing recorded yet"]));
  if (!pairs.length) $("history-compare").append(cells(["Share a thermostat and a temperature sensor in the same room"]));
}

const WHAT = { open: "Found", closed: "Over", sent: "Told", "not sent": "Could not be sent", acked: "Acknowledged", stopped: "Stopped", snoozed: "Snoozed" };
const FROM = { safety: "Safety", silent: "Silent sensor", rules: "Locks and doors", security: "Security", monitors: "Monitor", connection: "Connection", message: "Message", learning: "Learning", problems: "Problem", printers: "Printer", cameras: "Camera" };
let lastFinding = null;

function findingRow(item) {
  const row = element("li", undefined, item.severity), head = element("div", undefined, "head"), side = element("span");
  const told = item.told ? `told ${ago(item.told)}` : "not told", over = item.closed && !item.is_open ? `, over ${ago(item.closed)}` : "";
  const story = element("button", "Story", "quiet small"), hide = element("button", item.ignored ? "Show again" : "Hide", "quiet small");
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
  row.dataset.key = item.key || "";
  side.append(story, ...pressButtons(item, loadFindings), hide);
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

function safeDecode(text) {
  try { return decodeURIComponent(text); } catch { return ""; }
}

// Tapped from a phone message: that finding, with its story open.
async function showFinding(key) {
  const find = () => [...$("findings").children].find((row) => row.dataset.key === key);
  let row = find();
  if (!row && $("findings-show").value !== "closed") {
    $("findings-show").value = "closed";
    await loadFindings();
    row = find();
  }
  if (!row) return say("findings-message", "That message is no longer listed.");
  row.classList.add("picked");
  row.querySelector("button")?.click();
  row.scrollIntoView({ block: "center" });
}

// --- pages ---

const LOADERS = {
  overview: () => Promise.all([loadChat(), loadVoice(), loadHome()]),
  settings: () => Promise.all([loadStatus(), loadSettings(), loadVoice(), loadCameras(), loadRouter(), loadMemory()]),
  messages: () => Promise.all([loadMonitors(), loadMessages()]),
  findings: async () => say("findings-message", await loadFindings()), history: loadHistory,
  log: async () => say("log-message", await loadLog()), profile: loadProfile,
};
const MESSAGES = {
  overview: "overview-message", settings: "pair-message", messages: "messages-message",
  findings: "findings-message", history: "history-message", log: "log-message", profile: "session-message",
};

// A page with several sections shows one at a time, with tabs across the top.
const TABS = {
  settings: [["homes", "Homes"], ["model", "Model"], ["personality", "Personality"], ["voice", "Voice"], ["memory", "Memory"], ["cameras", "Cameras"], ["router", "Router"]],
  messages: [["messages", "Messages"], ["monitors", "Monitors"]],
};

function showTabs(page, wanted) {
  const tabs = TABS[page];
  document.getElementById("pages").classList.toggle("tabbed", Boolean(tabs));
  const bar = $("page-tabs");  // a div, not a nav: the main menu owns those
  if (!tabs) {
    bar.hidden = true;
    return;
  }
  const chosen = tabs.some(([place]) => place === wanted) ? wanted : (tabs.find(([place]) => place === seen.tab?.[page]) || tabs[0])[0];
  seen.tab = { ...(seen.tab || {}), [page]: chosen };
  bar.hidden = false;
  bar.replaceChildren(...tabs.map(([place, words]) => {
    const link = element("a", words);
    link.href = `#${place}`;
    if (place === chosen) link.setAttribute("aria-current", "page");
    return link;
  }));
  for (const [place] of tabs) $(`at-${place}`).hidden = place !== chosen;
}

// Like a command center's screens: panels fold into a line and go, then the next page's
// panels unfold one after another, with a moment of hologram flicker.
const calm = matchMedia("(prefers-reduced-motion: reduce)");
let shownPage = "";

async function foldAway(page) {
  if (calm.matches || !shownPage || shownPage === page || !document.body.classList.contains("command")) return;
  const going = [...document.querySelectorAll("#pages [data-page]:not([hidden]) .card, #pages [data-page]:not([hidden]) > h1")];
  for (const panel of going) panel.classList.add("folding");
  if (going.length) await new Promise((done) => setTimeout(done, 200));
  for (const panel of going) panel.classList.remove("folding");
}

function unfold(page) {
  const changed = shownPage !== page;
  shownPage = page;
  if (calm.matches || !changed || page === "overview") return;
  const coming = [...document.querySelectorAll(`#pages [data-page="${page}"]:not([hidden]) > h1, #pages [data-page="${page}"]:not([hidden]) .card:not([hidden])`)];
  coming.forEach((panel, i) => {
    panel.style.setProperty("--i", String(Math.min(i, 8)));
    panel.classList.remove("unfolding");
    void panel.offsetWidth;  // start the animation again
    panel.classList.add("unfolding");
    panel.addEventListener("animationend", () => panel.classList.remove("unfolding"), { once: true });
  });
}

async function openPage() {
  if (!signedIn) return;
  const wanted = location.hash.slice(1), target = wanted.startsWith("finding=") ? safeDecode(wanted.slice(8)) : null;
  const page = target !== null ? "findings" : PLACES[wanted] || (PAGES.includes(wanted) ? wanted : "overview");
  if (wanted === "messages") PLACES.messages = "messages";
  await foldAway(page);
  for (const section of document.querySelectorAll("[data-page]")) section.hidden = section.dataset.page !== page;
  showTabs(page, wanted);
  unfold(page);
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

    if (target !== null) await showFinding(target);
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
    deck.spell();  // BRAM's name forms as it answers you
    deck.say(reply.text);
    $("thought-facts").textContent = (reply.facts || []).slice(0, 3).join(" · ");
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
arrange();
try { setHue(localStorage.getItem("hue") || "cyan"); } catch { setHue("cyan"); }
try { setLook(localStorage.getItem("look") || "command"); } catch { setLook("command"); }
tick();
days();
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

onClick("memory-toggle", "memory-message", async () => {
  if (world.memoryOn) {
    const confirm = await askPassword("Turn memory off? BRAM stops keeping anything new.");
    const forget = window.confirm("Also forget everything BRAM remembers? Cancel keeps it, off and unused, until you turn memory on again.");
    showMemory(await api("memory-on", { confirm, on: false, forget }));
    return forget ? "Off, and everything is forgotten" : "Off. What was remembered is kept but not used";
  }
  const confirm = await askPassword("Turn memory on? BRAM keeps what you ask it to remember, and your conversation, on this server.");
  showMemory(await api("memory-on", { confirm, on: true }));
  return "Say \"Remember that...\" in chat to keep something.";
});
onClick("memory-forget", "memory-message", async () => {
  const confirm = await askPassword("Forget everything BRAM remembers, and your conversation? This cannot be undone.");
  showMemory(await api("memory-forget-all", { confirm }));
  return "Everything is forgotten";
});
onSubmit("memory-form", "memory-add", "memory-list-message", async () => {
  showMemory(await api("memory-add", { text: $("memory-text").value }));
  $("memory-text").value = "";
  return "Remembered";
});
onSubmit("router-form", "router-save", "router-message", async () => {
  const confirm = await askPassword("BRAM will read your router's device list and firmware status. It never changes the router.");
  showRouter(await api("router", { confirm, url: $("router-url").value, key: $("router-key").value, secret: $("router-secret").value }));
  $("router-key").value = "";
  return "Connected. The security check now sees every network.";
});
onClick("router-off", "router-message", async () => {
  const confirm = await askPassword("Disconnect the router? BRAM forgets its address and key.");
  showRouter(await api("router-off", { confirm }));
  return "Disconnected";
});
onSubmit("frigate-form", "frigate-save", "frigate-message", async () => {
  const confirm = await askPassword("BRAM will read Frigate's cameras and events. It never changes Frigate.");
  showCameras(await api("cameras", {
    confirm, url: $("frigate-url").value, user: $("frigate-user").value, password: $("frigate-password").value,
  }));
  return "Connected. Turn on the cameras BRAM should watch.";
});
$("camera-home").addEventListener("change", () => busy($("camera-home"), "camera-message", async () => {
  showCameras(await api("camera-home", { house: $("camera-home").value }));
  return "Saved. Only that home's Home Assistant gets these cameras.";
}));
onClick("frigate-off", "frigate-message", async () => {
  const confirm = await askPassword("Disconnect Frigate? BRAM forgets its address, login, and camera choices.");
  showCameras(await api("cameras-off", { confirm }));
  return "Disconnected";
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

onClick("history-start", "history-start-message", async () => {
  const confirm = await askPassword("BRAM will remember what your shared devices do, on this server.");
  await api("history", { confirm, on: true, limit_mb: Number($("history-limit").value),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
  await loadHistory();
  return "On. BRAM is keeping history from now on.";
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

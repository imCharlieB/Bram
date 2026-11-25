"use strict";
const $ = (id) => document.getElementById(id);
const PAGES = ["overview", "messages", "settings", "log", "profile"];
// Places inside a page.
const PLACES = { homes: "settings", model: "settings", personality: "settings", monitors: "messages" };
const STORY = {
  connected: "Home Assistant connected", disconnected: "Home Assistant disconnected", paired: "A home was paired",
  unpaired: "A home was removed", "signed in": "You signed in", "login refused": "Someone entered a wrong login",
  "setup refused": "A setup attempt was refused", "settings saved": "Settings changed", "login created": "Your login was created",
  "code created": "A pairing code was made", "password changed": "Your password changed", "username changed": "Your username changed",
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

async function loadStatus() {
  const { houses, version } = await api("status");
  $("version").textContent = `BRAM Server ${version}`;
  paired = houses.length > 0;
  loadSteps();
  world.houses = houses;
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
  const { user, sessions } = await api("profile");
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
    row.append(element("span", `${item.name} (${item.url})`), side);
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
  $("ntfy-topic").hidden = $("ntfy-help").hidden = !ntfy.topic;
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

const world = { houses: [], monitors: [] };

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
  $("hero").classList.toggle("worried", Boolean(problem) || down.length > 0);
  if (problem) {
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

async function loadChat() {
  const { messages } = await api("chat");
  $("chat-log").replaceChildren();
  $("chat-clear").hidden = true;
  for (const message of messages) bubble(message.role, message.text);
}

async function loadHome() {
  let problem = "";
  try {
    await Promise.all([loadStatus(), loadMonitors(), loadSettings(), loadLatest()]);
  } catch (error) {
    problem = error.message;
  }
  headline(problem);
}

setInterval(() => {
  if (signedIn && !document.hidden && !$("overview-message").closest("section").hidden) loadHome();
}, 60000);

// --- pages ---

const LOADERS = {
  overview: () => Promise.all([loadChat(), loadHome()]),
  settings: () => Promise.all([loadStatus(), loadSettings()]),
  messages: () => Promise.all([loadMonitors(), loadMessages()]),
  log: async () => say("log-message", await loadLog()), profile: loadProfile,
};
const MESSAGES = {
  overview: "overview-message", settings: "pair-message", messages: "messages-message",
  log: "log-message", profile: "session-message",
};

async function openPage() {
  if (!signedIn) return;
  const wanted = location.hash.slice(1), page = PLACES[wanted] || (PAGES.includes(wanted) ? wanted : "overview");
  for (const section of document.querySelectorAll("[data-page]")) section.hidden = section.dataset.page !== page;
  for (const link of document.querySelectorAll("nav a:not(.brand)")) {
    if (link.hash === "#" + page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  // Never leave a pairing code or a typed password behind.
  $("code-box").hidden = true;
  $("code").textContent = "";
  $("sample").hidden = true;
  $("tg-link-box").hidden = true;
  $("change-form").reset();
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
  const password = $("password").value;
  $("password").value = "";
  await api("login", { user: $("user").value, password });
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
  $("hero").classList.add("thinking");
  try {
    const reply = await api("chat", { text, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
    bubble("assistant", reply.text, reply.facts);
  } catch (error) {
    mine.remove();
    if (!$("chat-text").value) $("chat-text").value = text;
    throw error;
  } finally {
    $("hero").classList.remove("thinking");
    $("chat-text").focus();
  }
});
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
  const port = { ollama: 11434, frigate: 5000, device: 80 }[$("monitor-kind").value];
  $("monitor-url").placeholder = `http://HOST:${port}`;
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
  $("chat-log").replaceChildren();
  try { await api("logout", {}); } finally { location.assign("/ui/"); }
});

onClick("logout-others", "session-message", async () => {
  await api("logout-others", {});
  await loadProfile();
  return "Every other device has been signed out.";
});

start().catch((error) => { show("login"); say("login-message", error.message, "bad"); });

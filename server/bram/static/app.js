"use strict";
const $ = (id) => document.getElementById(id);
const PAGES = ["overview", "homes", "model", "personality", "log", "profile"];
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
  $("tile-homes").textContent = `${houses.filter((house) => house.connected).length} of ${houses.length}`;
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

async function loadLatest() {
  const { entries } = await api("log?limit=5");
  $("latest").replaceChildren(...(entries.length ? entries.map((entry) => {
    const row = element("li");
    row.append(element("span", `${entry.decision.replaceAll("_", " ")}: ${entry.reason}`),
      element("span", new Date(entry.at * 1000).toLocaleString(), "note"));
    return row;
  }) : [element("li", "Nothing yet")]));
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

// --- pages ---

const LOADERS = {
  overview: () => Promise.all([loadStatus(), loadSettings(), loadLatest()]),
  homes: loadStatus, model: loadSettings, personality: loadSettings,
  log: async () => say("log-message", await loadLog()), profile: loadProfile,
};
const MESSAGES = {
  overview: "overview-message", homes: "pair-message", model: "model-message",
  personality: "personality-message", log: "log-message", profile: "session-message",
};

async function openPage() {
  if (!signedIn) return;
  const wanted = location.hash.slice(1), page = PAGES.includes(wanted) ? wanted : "overview";
  for (const section of document.querySelectorAll("[data-page]")) section.hidden = section.dataset.page !== page;
  for (const link of document.querySelectorAll("nav a:not(.brand)")) {
    if (link.hash === "#" + page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  // Never leave a pairing code or a typed password behind.
  $("code-box").hidden = true;
  $("code").textContent = "";
  $("sample").hidden = true;
  $("change-form").reset();
  for (const node of document.querySelectorAll("#pages .message")) say(node.id, "");
  scrollTo(0, 0);
  try {
    await LOADERS[page]();
  } catch (error) {
    say(MESSAGES[page], error.message, "bad");
  }
}

async function start() {
  const state = await api("state");
  if (!state.login_exists) return show(state.setup_open ? "setup" : "closed");
  if (!state.signed_in) return show("login");
  show("app");
  await Promise.all([loadProfile(), openPage()]);
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
  try { await api("logout", {}); } finally { location.assign("/ui/"); }
});

onClick("logout-others", "session-message", async () => {
  await api("logout-others", {});
  await loadProfile();
  return "Every other device has been signed out.";
});

start().catch((error) => { show("login"); say("login-message", error.message, "bad"); });

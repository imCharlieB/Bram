"use strict";
const $ = (id) => document.getElementById(id);

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
  for (const id of ["setup", "closed", "login", "app"]) $(id).hidden = id !== name;
  $("logout").hidden = name !== "app";
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

let paired = false, modelSaved = false;

function loadSteps() {
  const steps = [["Create your login", true], ["Connect Home Assistant", paired],
    ["Choose a model (needed for personality)", modelSaved]];
  $("start").hidden = steps.every(([, done]) => done);
  $("steps").replaceChildren(...steps.map(([text, done]) => {
    const row = element("li");
    row.append(element("span", text), element("span", done ? "Done" : "To do", done ? "good" : ""));
    return row;
  }));
}

async function loadStatus() {
  const { houses, version } = await api("status");
  $("version").textContent = `BRAM Server ${version}`;
  paired = houses.length > 0;
  loadSteps();
  $("houses").replaceChildren(...(houses.length ? houses.map((house) => {
    const row = element("li"), side = element("span"), remove = element("button", "Remove", "quiet small");
    remove.addEventListener("click", async () => {
      await busy(remove, "pair-message", async () => {
        const confirm = await askPassword(`Remove ${house.name}? It will need a new code to return.`);
        await api("unpair", { house_id: house.id, confirm });
        await loadStatus();
        return "Removed";
      });
    });
    side.append(element("span", house.connected ? "Connected" : "Not connected", house.connected ? "good" : "bad"), remove);
    row.append(element("span", house.name), side);
    return row;
  }) : [element("li", "None yet")]));
}

async function loadLog() {
  const { entries } = await api("log");
  $("log").replaceChildren(...entries.map((entry) => {
    const row = element("tr");
    row.append(element("td", new Date(entry.at * 1000).toLocaleString()), element("td", entry.house),
      element("td", entry.decision.replaceAll("_", " ")), element("td", entry.trigger + ": " + entry.reason));
    return row;
  }));
}

async function loadSettings() {
  const { settings, modes, custom_limit } = await api("settings");
  modelSaved = Boolean(settings.model);
  loadSteps();
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

async function start() {
  const state = await api("state");
  if (!state.login_exists) return show(state.setup_open ? "setup" : "closed");
  if (!state.signed_in) return show("login");
  show("app");
  await Promise.all([loadStatus(), loadSettings(), loadLog()]);
}

$("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy($("create"), "setup-message", async () => {
    const password = $("new-password").value;
    if (password !== $("new-again").value) throw new Error("The passwords do not match");
    await api("setup", { user: $("new-user").value, password });
    $("setup-form").reset();
    await start();
  });
});
$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const password = $("password").value;
  $("password").value = "";
  busy($("signin"), "login-message", async () => {
    await api("login", { user: $("user").value, password });
    await start();
  });
});
$("change-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy($("change"), "change-message", async () => {
    const password = $("change-new").value;
    if (password !== $("change-again").value) throw new Error("The passwords do not match");
    const confirm = await askPassword("Enter your current password.");
    await api("password", { new: password, confirm });
    $("change-form").reset();
    return "Changed. Every other device has been signed out.";
  });
});
$("pair-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy($("pair"), "pair-message", async () => {
    const confirm = await askPassword("This lets a Home Assistant connect to BRAM.");
    const { code, minutes } = await api("pair", { name: $("home").value, confirm });
    $("code").textContent = code;
    $("address").textContent = location.hostname;
    $("port").textContent = location.port || "443";
    $("minutes").textContent = minutes;
    $("code-box").hidden = false;
  });
});
$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("code").textContent);
    say("pair-message", "Copied", "good");
  } catch {
    say("pair-message", "Select the code and copy it by hand", "bad");
  }
});
$("logout").addEventListener("click", async () => {
  try { await api("logout", {}); } finally { location.reload(); }
});
$("modes").addEventListener("change", () => {
  $("custom-box").hidden = personality().personality !== "custom";
});
$("find").addEventListener("click", () => busy($("find"), "model-message", async () => {
  const { models } = await api("models", { url: $("url").value });
  fillModels(models, models.includes($("model").value) ? $("model").value : models[0]);
  return models.length ? `Found ${models.length}` : "No local models found there";
}));
$("save-model").addEventListener("click", () => busy($("save-model"), "model-message", async () => {
  const confirm = await askPassword("The model will see what BRAM says about your home.");
  await api("settings", {
    confirm, model_url: $("url").value, model: $("model").value, context: Number($("context").value),
  });
  modelSaved = Boolean($("model").value);
  loadSteps();
  return "Saved";
}));
$("save-personality").addEventListener("click", () => busy($("save-personality"), "personality-message", async () => {
  await api("settings", personality());
  return "Saved";
}));
$("try").addEventListener("click", () => busy($("try"), "personality-message", async () => {
  $("sample").hidden = true;
  const { text } = await api("sample", personality());
  $("sample").textContent = text || "(The model said nothing)";
  $("sample").hidden = false;
}));
$("refresh").addEventListener("click", () => { loadLog().catch(() => {}); loadStatus().catch(() => {}); });

start().catch((error) => { show("login"); say("login-message", error.message, "bad"); });

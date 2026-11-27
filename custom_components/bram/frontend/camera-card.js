// BRAM camera card for Home Assistant dashboards: what the cameras saw, newest first, grouped
// by day, each with Frigate's picture and BRAM's words. It only shows; it changes nothing.
// Text is set with textContent only.

const STYLE = `
  :host { display: block; color: var(--primary-text-color); }
  ha-card { padding: 12px 0 6px; overflow: hidden; }
  h2 { margin: 0; padding: 4px 16px 8px; font-size: 1.05rem; font-weight: 500; }
  .list { max-height: var(--bram-height, 420px); overflow-y: auto; scrollbar-width: thin; }
  h3 { margin: 0; padding: 10px 16px 4px; font-size: .9rem; font-weight: 500; color: var(--secondary-text-color); }
  .row { display: grid; grid-template-columns: 40px 1fr auto; gap: 12px; align-items: center; padding: 8px 16px; }
  .icon { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 50%; background: var(--secondary-background-color); color: var(--secondary-text-color); --mdc-icon-size: 22px; }
  .text { display: grid; gap: 2px; min-width: 0; }
  .title { font-weight: 500; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .meta { color: var(--secondary-text-color); font-size: .85rem; }
  .words { color: var(--secondary-text-color); font-size: .85rem; line-height: 1.35; }
  img, .noimg { width: 76px; height: 76px; border-radius: 10px; object-fit: cover; background: var(--secondary-background-color); }
  .note { padding: 8px 16px 12px; color: var(--secondary-text-color); }
  .error { color: var(--error-color); }
`;

const EVERY = 10000;
const ICONS = { person: "mdi:walk", car: "mdi:car", truck: "mdi:truck", motorcycle: "mdi:motorbike", bicycle: "mdi:bicycle", package: "mdi:package-variant-closed", dog: "mdi:dog", cat: "mdi:cat", bird: "mdi:bird" };

function cameraName(name) {
  const words = name.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function day(seconds) {
  const then = new Date(seconds * 1000), today = new Date();
  const start = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((start(today) - start(then)) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return then.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

class BramCameraCard extends HTMLElement {
  setConfig(config) {
    if (config.camera !== undefined && typeof config.camera !== "string") throw new Error("camera must be a Frigate camera name");
    if (config.count !== undefined && !(Number.isInteger(config.count) && config.count >= 1 && config.count <= 20)) throw new Error("count must be 1 to 20");
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._load();
      this._timer = setInterval(() => this._load(), EVERY);
    }
  }

  connectedCallback() {
    if (this._hass && !this._timer) this._timer = setInterval(() => this._load(), EVERY);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._timer = undefined;
  }

  getCardSize() {
    return 1 + Math.min(this._config?.count || 5, 6);
  }

  static getStubConfig() {
    return { count: 5 };
  }

  el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  async _load() {
    if (!this._hass) return;
    try {
      const { cameras } = await this._hass.callWS({ type: "bram/cameras" });
      this._cameras = cameras;
      this._error = "";
    } catch (error) {
      this._error = error.message || "BRAM is not running.";
    }
    this._render();
  }

  _row(item) {
    const row = this.el("div", undefined, "row"), icon = this.el("div", undefined, "icon"), text = this.el("div", undefined, "text");
    const symbol = document.createElement("ha-icon");
    symbol.icon = ICONS[item.label] || "mdi:cctv";
    icon.append(symbol);
    const said = item.who ? `${item.who} at ${cameraName(item.camera).toLowerCase()}` : item.summary;
    text.append(this.el("div", said.charAt(0).toUpperCase() + said.slice(1), "title"));
    const time = new Date(item.start * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    text.append(this.el("div", `${time} • ${cameraName(item.camera)}${item.zones.length ? ` • ${item.zones.join(", ").replaceAll("_", " ")}` : ""}`, "meta"));
    if (item.description) text.append(this.el("div", item.description, "words"));
    row.append(icon, text);
    if (item.image) {
      const img = this.el("img");
      img.src = item.image;
      img.alt = said;
      img.loading = "lazy";
      img.addEventListener("error", () => img.replaceWith(this.el("div", undefined, "noimg")));
      row.append(img);
    } else {
      row.append(this.el("div", undefined, "noimg"));
    }
    return row;
  }

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = STYLE;
      this._card = document.createElement("ha-card");
      this.shadowRoot.append(style, this._card);
    }
    const all = this._cameras || [];
    const wanted = this._config.camera;
    const parts = [];
    if (this._config.title !== "") parts.push(this.el("h2", this._config.title || (wanted ? cameraName(wanted) : "Cameras")));
    if (this._error) {
      parts.push(this.el("div", this._error, "note error"));
    } else if (!this._cameras) {
      parts.push(this.el("div", "Loading...", "note"));
    } else {
      const chosen = wanted ? all.filter((c) => c.name === wanted) : all;
      if (!chosen.length) {
        parts.push(this.el("div", wanted ? `BRAM does not watch a camera named ${wanted}. Turn it on under Settings, Cameras on BRAM's page.` : "BRAM watches no cameras yet. Turn them on under Settings, Cameras on BRAM's page.", "note"));
      } else {
        const events = chosen.flatMap((c) => (c.events || (c.event ? [{ ...c.event, image: c.image }] : [])).map((e) => ({ ...e, camera: c.name })))
          .sort((a, b) => b.start - a.start).slice(0, this._config.count || 5);
        if (!events.length) parts.push(this.el("div", "Nothing yet.", "note"));
        const list = this.el("div", undefined, "list");
        let heading = "";
        for (const item of events) {
          const when = day(item.start);
          if (when !== heading) {
            heading = when;
            list.append(this.el("h3", when));
          }
          list.append(this._row(item));
        }
        if (events.length) parts.push(list);
      }
    }
    this._card.replaceChildren(...parts);
  }
}

if (!customElements.get("bram-camera-card")) customElements.define("bram-camera-card", BramCameraCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "bram-camera-card")) {
  window.customCards.push({ type: "bram-camera-card", name: "BRAM camera", description: "What your cameras saw, newest first, with Frigate's pictures and BRAM's descriptions." });
}

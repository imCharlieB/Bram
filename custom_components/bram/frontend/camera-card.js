// BRAM camera card for Home Assistant dashboards: Frigate's picture with BRAM's words.
// It only shows; it changes nothing. Text is set with textContent only.

const STYLE = `
  :host { display: block; color: var(--primary-text-color); }
  ha-card { overflow: hidden; }
  .head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; padding: 12px 16px 8px; }
  .head h2 { margin: 0; font-size: 1.1rem; font-weight: 500; }
  .head small { color: var(--secondary-text-color); }
  img { display: block; width: 100%; max-height: 320px; object-fit: cover; background: var(--secondary-background-color); }
  .body { display: grid; gap: 6px; padding: 10px 16px 14px; }
  .what { font-weight: 500; }
  .words { margin: 0; line-height: 1.45; border-left: 3px solid var(--primary-color); padding-left: 10px; }
  .note { color: var(--secondary-text-color); font-size: .86rem; }
  .error { color: var(--error-color); }
`;

const EVERY = 10000;

function cameraName(name) {
  const words = name.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function ago(seconds) {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return new Date(seconds * 1000).toLocaleDateString();
}

class BramCameraCard extends HTMLElement {
  setConfig(config) {
    if (config.camera !== undefined && typeof config.camera !== "string") throw new Error("camera must be a Frigate camera name");
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

  disconnectedCallback() {
    clearInterval(this._timer);
    this._timer = undefined;
    this._hass = undefined;
  }

  getCardSize() {
    return 5;
  }

  static getStubConfig() {
    return {};
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
    const camera = wanted ? all.find((c) => c.name === wanted)
      : all.filter((c) => c.event).sort((a, b) => b.event.start - a.event.start)[0] || all[0];
    const head = this.el("div", undefined, "head");
    head.append(this.el("h2", this._config.title || (camera ? cameraName(camera.name) : "Cameras")));
    const body = this.el("div", undefined, "body");
    const parts = [head];
    if (this._error) {
      body.append(this.el("p", this._error, "error"));
    } else if (!this._cameras) {
      body.append(this.el("p", "Loading...", "note"));
    } else if (!camera) {
      body.append(this.el("p", wanted ? `BRAM does not watch a camera named ${wanted}. Turn it on under Settings, Cameras on BRAM's page.` : "BRAM watches no cameras yet. Turn them on under Settings, Cameras on BRAM's page.", "note"));
    } else if (!camera.event) {
      body.append(this.el("p", "Nothing yet.", "note"));
    } else {
      const event = camera.event;
      head.append(this.el("small", ago(event.start)));
      if (camera.image) {
        const img = this.el("img");
        img.src = camera.image;
        img.alt = event.summary;
        img.addEventListener("error", () => img.remove());
        parts.push(img);
      }
      body.append(this.el("div", event.summary.charAt(0).toUpperCase() + event.summary.slice(1), "what"));
      if (event.description) body.append(this.el("p", event.description, "words"));
      if (!camera.image) body.append(this.el("p", "Install the Frigate integration for the picture.", "note"));
    }
    parts.push(body);
    this._card.replaceChildren(...parts);
  }
}

if (!customElements.get("bram-camera-card")) customElements.define("bram-camera-card", BramCameraCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "bram-camera-card")) {
  window.customCards.push({ type: "bram-camera-card", name: "BRAM camera", description: "Frigate's picture of the latest event, with BRAM's description." });
}

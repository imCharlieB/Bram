// BRAM's review page in Home Assistant. Shows what BRAM suggests and what would change.
// Only an admin signed in to Home Assistant can answer. Text is set with textContent only.

const STYLE = `
  :host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  header { display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 56px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); }
  header h1 { margin: 0; font-size: 20px; font-weight: 400; flex: 1; }
  header a { color: inherit; text-decoration: none; font-size: 14px; }
  main { max-width: 720px; margin: 0 auto; padding: 16px; }
  .card { background: var(--card-background-color); border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.2)); }
  h2 { margin: 0 0 8px; font-size: 18px; font-weight: 500; }
  p { line-height: 1.5; margin: 8px 0; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th, td { text-align: left; padding: 8px 4px; border-bottom: 1px solid var(--divider-color); }
  th { font-weight: 500; color: var(--secondary-text-color); font-size: 13px; }
  .note { color: var(--secondary-text-color); font-size: 13px; }
  .buttons { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  button { font: inherit; padding: 10px 18px; border-radius: 20px; border: 1px solid var(--primary-color); background: transparent; color: var(--primary-color); cursor: pointer; }
  button.main { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  button:disabled { opacity: .5; cursor: default; }
  .error { color: var(--error-color); }
`;

class BramReview extends HTMLElement {
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this.load();
  }

  set narrow(value) {}
  set panel(value) {}

  connectedCallback() {
    if (this.shadowRoot) return;
    const root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLE;
    const header = document.createElement("header");
    const title = document.createElement("h1");
    title.textContent = "BRAM suggestions";
    const close = document.createElement("a");
    close.href = "/";
    close.textContent = "Close";
    header.append(title, close);
    this._main = document.createElement("main");
    root.append(style, header, this._main);
    if (this._hass) this.load();
  }

  el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  async load() {
    if (!this._main || !this._hass) return;
    try {
      const { items } = await this._hass.callWS({ type: "bram/review/list" });
      this.show(items);
    } catch (error) {
      this._main.replaceChildren(this.el("p", error.message || "BRAM is not running.", "error"));
    }
  }

  show(items) {
    if (!items.length) {
      const card = this.el("div", undefined, "card");
      card.append(this.el("h2", "Nothing waiting"), this.el("p", "When BRAM has a suggestion, your phone gets a message that opens this page."));
      this._main.replaceChildren(card);
      return;
    }
    this._main.replaceChildren(...items.map((item) => this.card(item)));
  }

  card(item) {
    const card = this.el("div", undefined, "card");
    card.append(this.el("h2", item.title), this.el("p", item.text));
    if (item.changes.length) {
      const table = this.el("table");
      const head = this.el("tr");
      head.append(this.el("th", "Setting"), this.el("th", "Now"), this.el("th", "Would be"));
      table.append(head, ...item.changes.map((change) => {
        const row = this.el("tr");
        row.append(this.el("td", change.name), this.el("td", change.now), this.el("td", change.new));
        return row;
      }));
      card.append(table);
    }
    card.append(this.el("p", `Nothing changes unless you approve. Waits until ${new Date(item.expires * 1000).toLocaleDateString()}. You can undo an approved change under BRAM, Configure, Learning.`, "note"));
    const buttons = this.el("div", undefined, "buttons"), message = this.el("p", "", "error");
    for (const [answer, words, main] of [["approve", "Approve", true], ["later", "Not now"], ["never", "Never suggest this"]]) {
      const button = this.el("button", words, main ? "main" : "");
      button.addEventListener("click", async () => {
        for (const other of buttons.children) other.disabled = true;
        try {
          await this._hass.callWS({ type: "bram/review/answer", item: item.id, answer });
          await this.load();
        } catch (error) {
          message.textContent = error.message || "Could not answer.";
          await this.load();
        }
      });
      buttons.append(button);
    }
    card.append(buttons, message);
    return card;
  }
}

customElements.define("bram-review", BramReview);

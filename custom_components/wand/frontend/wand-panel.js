// Wand sidebar page: the floor plan, the devices the wand may control, and the spellbook.
// Plain custom element, no build step, so it ships inside the integration as-is.

const DOMAIN_ICONS = {
  light: "mdi:lightbulb",
  switch: "mdi:toggle-switch",
  fan: "mdi:fan",
  media_player: "mdi:television",
  cover: "mdi:blinds",
  climate: "mdi:thermostat",
};

const ERROR_TEXT = {
  not_allowed: "Not allowed",
  unsupported: "Not supported",
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const domainOf = (entityId) => entityId.split(".")[0];

class WandPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._imageUrl = null;
    this._imageAspect = null;
    this._edit = false;
    this._dialog = null; // {kind: "device" | "spot" | "spellbook" | "add", id}
    this._error = null;
    this._loading = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._load();
    } else {
      this._refreshStates();
    }
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
  }

  get _isAdmin() {
    return Boolean(this._hass?.user?.is_admin);
  }

  // Data

  async _load() {
    this._loading = true;
    this._render();
    try {
      this._config = await this._hass.callWS({ type: "wand/config" });
      await this._loadImage();
      this._error = null;
    } catch (err) {
      this._error = err?.message || "Couldn't load the Wand settings";
    }
    this._loading = false;
    this._render();
  }

  async _loadImage() {
    if (this._imageUrl) URL.revokeObjectURL(this._imageUrl);
    this._imageUrl = null;
    if (!this._config?.floorplan?.filename) return;
    const response = await this._hass.fetchWithAuth("/api/wand/floorplan");
    if (!response.ok) return;
    this._imageUrl = URL.createObjectURL(await response.blob());
  }

  async _ws(message) {
    try {
      this._config = await this._hass.callWS(message);
      this._error = null;
    } catch (err) {
      this._error = err?.message || "Couldn't save";
    }
    this._render();
  }

  _devices() {
    return Object.entries(this._config?.devices || {}).map(([entityId, device]) => ({ entityId, ...device }));
  }

  _name(entityId) {
    const state = this._hass.states[entityId];
    return state?.attributes?.friendly_name || entityId;
  }

  _spellsFor(entityId) {
    const domain = domainOf(entityId);
    return (this._config?.spells || []).filter((s) => s.domains.includes(domain) || s.domains.includes("*"));
  }

  _allowedSpellIds(device) {
    const usable = this._spellsFor(device.entityId).map((s) => s.id);
    return device.spells == null ? usable : usable.filter((id) => device.spells.includes(id));
  }

  // Rendering

  _render() {
    const root = this.shadowRoot;
    if (!this._hass) return;
    const devices = this._devices();
    const allowed = devices.filter((d) => d.enabled);
    const blocked = devices.filter((d) => !d.enabled);
    const aspect = this._config?.floorplan?.aspect || this._imageAspect || 0.6;

    root.innerHTML = `
      <style>${STYLES}</style>
      <div class="toolbar">
        ${this._narrow ? `<ha-menu-button></ha-menu-button>` : ""}
        <div class="title">Wand</div>
        <div class="spacer"></div>
        ${this._isAdmin ? `
          <button class="btn" data-action="spellbook"><ha-icon icon="mdi:book-open-variant"></ha-icon><span>Spellbook</span></button>
          <button class="btn ${this._edit ? "on" : ""}" data-action="toggle-edit">
            <ha-icon icon="${this._edit ? "mdi:check" : "mdi:pencil"}"></ha-icon><span>${this._edit ? "Done" : "Edit"}</span>
          </button>` : ""}
      </div>
      <div class="content">
        ${this._error ? `<div class="error">${esc(this._error)}</div>` : ""}
        ${this._loading ? `<div class="hint">Loading…</div>` : ""}
        ${this._edit ? `
          <div class="editbar">
            <label class="btn"><ha-icon icon="mdi:image-plus"></ha-icon><span>${this._imageUrl ? "Replace floor plan" : "Upload floor plan"}</span>
              <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" data-action="upload" hidden></label>
            <button class="btn" data-action="add-device"><ha-icon icon="mdi:plus"></ha-icon><span>Add device</span></button>
            <button class="btn" data-action="add-spot"><ha-icon icon="mdi:account-voice"></ha-icon><span>Add casting spot</span></button>
            <span class="hint">Drag icons to where the devices are. Click one to set what the wand may do.</span>
          </div>` : ""}
        <div class="card">
          <div class="plan ${this._edit ? "editing" : ""}" style="aspect-ratio: ${aspect}; width: min(100%, calc(80vh * ${aspect}))">
            ${this._imageUrl
              ? `<img src="${this._imageUrl}" alt="Floor plan" draggable="false">`
              : `<div class="empty">${this._isAdmin ? "Click Edit, then Upload floor plan to start." : "No floor plan yet."}</div>`}
            ${devices.map((d) => this._markerHtml(d)).join("")}
            ${(this._config?.spots || []).map((s) => this._spotHtml(s)).join("")}
          </div>
        </div>
        <div class="card list">
          <div class="list-head">Wand can control <b>${allowed.length}</b> device${allowed.length === 1 ? "" : "s"}${blocked.length ? ` · ${blocked.length} not allowed` : ""}</div>
          ${devices.length === 0 ? `<div class="hint">No devices placed yet.</div>` : ""}
          ${[...allowed, ...blocked].map((d) => this._rowHtml(d)).join("")}
        </div>
      </div>
      ${this._dialogHtml()}
    `;

    this._bind();
    this._refreshStates();
    const menu = root.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
  }

  _markerHtml(d) {
    return `
      <div class="marker ${d.enabled ? "allowed" : "blocked"}" data-entity="${esc(d.entityId)}"
           style="left:${d.x * 100}%;top:${d.y * 100}%" title="${esc(this._name(d.entityId))}">
        <ha-icon data-icon-for="${esc(d.entityId)}"></ha-icon>
        ${d.enabled ? "" : `<span class="slash"></span>`}
      </div>`;
  }

  _spotHtml(s) {
    return `
      <div class="spot" data-spot="${esc(s.id)}" style="left:${s.x * 100}%;top:${s.y * 100}%" title="Casting spot: ${esc(s.name)}">
        <ha-icon icon="mdi:account-voice"></ha-icon><span>${esc(s.name)}</span>
      </div>`;
  }

  _rowHtml(d) {
    const spells = this._allowedSpellIds(d)
      .map((id) => this._config.spells.find((s) => s.id === id)?.name)
      .filter(Boolean);
    return `
      <div class="row ${d.enabled ? "" : "muted"}" data-row="${esc(d.entityId)}">
        <ha-icon data-icon-for="${esc(d.entityId)}"></ha-icon>
        <div class="row-text">
          <div>${esc(this._name(d.entityId))}</div>
          <div class="sub">${d.enabled ? esc(spells.join(", ") || "No spells") : "Not allowed"}</div>
        </div>
        <ha-icon class="chev" icon="mdi:chevron-right"></ha-icon>
      </div>`;
  }

  _refreshStates() {
    const root = this.shadowRoot;
    if (!root || !this._hass) return;
    root.querySelectorAll("[data-icon-for]").forEach((el) => {
      const entityId = el.getAttribute("data-icon-for");
      const state = this._hass.states[entityId];
      el.setAttribute("icon", state?.attributes?.icon || DOMAIN_ICONS[domainOf(entityId)] || "mdi:help-circle");
      const host = el.closest(".marker, .row");
      if (host) host.classList.toggle("active", state?.state === "on" || state?.state === "playing" || state?.state === "open");
    });
  }

  _dialogHtml() {
    const dialog = this._dialog;
    if (!dialog) return "";
    let body = "";
    if (dialog.kind === "device") body = this._deviceDialog(dialog.id);
    if (dialog.kind === "spot") body = this._spotDialog(dialog.id);
    if (dialog.kind === "spellbook") body = this._spellbookDialog();
    if (dialog.kind === "add") body = this._addDialog();
    return `<div class="scrim" data-action="close"></div><div class="dialog" role="dialog">${body}</div>`;
  }

  _deviceDialog(entityId) {
    const device = this._config.devices[entityId];
    if (!device) return "";
    const d = { entityId, ...device };
    const allowedIds = this._allowedSpellIds(d);
    const admin = this._isAdmin;
    return `
      <div class="dialog-head"><ha-icon data-icon-for="${esc(entityId)}"></ha-icon><div><b>${esc(this._name(entityId))}</b><div class="sub">${esc(entityId)} · ${esc(this._hass.states[entityId]?.state ?? "unknown")}</div></div></div>
      <label class="switch-row"><span>Wand may control this device</span>
        <input type="checkbox" data-action="toggle-enabled" ${d.enabled ? "checked" : ""} ${admin ? "" : "disabled"}></label>
      <div class="section-title">Spells it accepts</div>
      <div class="spells">
        ${this._spellsFor(entityId).map((s) => `
          <label class="spell ${d.enabled ? "" : "muted"}">
            <input type="checkbox" data-spell="${esc(s.id)}" ${allowedIds.includes(s.id) ? "checked" : ""} ${admin && d.enabled ? "" : "disabled"}>
            <span>${esc(s.name)}</span><span class="sub">${s.gesture ? "gesture" : esc(s.words.join(", "))}</span>
          </label>`).join("")}
      </div>
      <div class="dialog-actions">
        ${admin && this._edit ? `<button class="btn danger" data-action="remove-device">Remove from plan</button>` : ""}
        <button class="btn" data-action="more-info">Device details</button>
        <div class="spacer"></div>
        <button class="btn primary" data-action="close">Close</button>
      </div>`;
  }

  _spotDialog(spotId) {
    const spot = (this._config.spots || []).find((s) => s.id === spotId);
    if (!spot) return "";
    return `
      <div class="dialog-head"><ha-icon icon="mdi:account-voice"></ha-icon><b>Casting spot</b></div>
      <p class="sub">Where you stand when you calibrate the wand. The watch remembers device directions from here.</p>
      <label class="field"><span>Name</span><input type="text" data-field="spot-name" value="${esc(spot.name)}" maxlength="40"></label>
      <div class="dialog-actions">
        <button class="btn danger" data-action="remove-spot">Remove</button>
        <div class="spacer"></div>
        <button class="btn primary" data-action="save-spot">Save</button>
      </div>`;
  }

  _spellbookDialog() {
    const spells = (this._config.spells || []).filter((s) => !s.gesture);
    return `
      <div class="dialog-head"><ha-icon icon="mdi:book-open-variant"></ha-icon><b>Spellbook</b></div>
      <p class="sub">The words you say for each spell. Separate alternatives with commas, for example "lumos, light".</p>
      ${spells.map((s) => `
        <label class="field"><span>${esc(s.name)}</span>
          <input type="text" data-words="${esc(s.id)}" value="${esc(s.words.join(", "))}"></label>`).join("")}
      <div class="dialog-actions"><div class="spacer"></div>
        <button class="btn" data-action="close">Cancel</button>
        <button class="btn primary" data-action="save-spellbook">Save</button></div>`;
  }

  _addDialog() {
    const placed = new Set(Object.keys(this._config.devices || {}));
    const supported = new Set(this._config.supported_domains || []);
    const options = Object.keys(this._hass.states)
      .filter((id) => supported.has(domainOf(id)) && !placed.has(id))
      .sort((a, b) => this._name(a).localeCompare(this._name(b)));
    return `
      <div class="dialog-head"><ha-icon icon="mdi:plus"></ha-icon><b>Add a device to the plan</b></div>
      <label class="field"><span>Device</span>
        <select data-field="add-entity">
          ${options.map((id) => `<option value="${esc(id)}">${esc(this._name(id))} (${esc(id)})</option>`).join("")}
        </select></label>
      ${options.length === 0 ? `<p class="sub">Every supported device is already on the plan.</p>` : ""}
      <div class="dialog-actions"><div class="spacer"></div>
        <button class="btn" data-action="close">Cancel</button>
        <button class="btn primary" data-action="confirm-add" ${options.length ? "" : "disabled"}>Add</button></div>`;
  }

  // Events

  _bind() {
    const root = this.shadowRoot;
    root.querySelectorAll("[data-action]").forEach((el) => {
      const action = el.getAttribute("data-action");
      const type = action === "upload" || action === "toggle-enabled" ? "change" : "click";
      el.addEventListener(type, (ev) => this._onAction(action, ev));
    });
    root.querySelectorAll("[data-spell]").forEach((el) =>
      el.addEventListener("change", () => this._saveDeviceSpells()));
    root.querySelectorAll(".marker").forEach((el) => this._bindDrag(el, "entity"));
    root.querySelectorAll(".spot").forEach((el) => this._bindDrag(el, "spot"));
    root.querySelectorAll("[data-row]").forEach((el) =>
      el.addEventListener("click", () => this._open({ kind: "device", id: el.getAttribute("data-row") })));
  }

  _open(dialog) {
    this._dialog = dialog;
    this._render();
  }

  async _onAction(action, ev) {
    const dialog = this._dialog;
    switch (action) {
      case "toggle-edit":
        this._edit = !this._edit;
        this._render();
        break;
      case "spellbook":
        this._open({ kind: "spellbook" });
        break;
      case "close":
        this._dialog = null;
        this._render();
        break;
      case "upload":
        await this._upload(ev.target.files?.[0]);
        break;
      case "add-device":
        this._open({ kind: "add" });
        break;
      case "confirm-add": {
        const entityId = this.shadowRoot.querySelector("[data-field='add-entity']").value;
        this._dialog = { kind: "device", id: entityId };
        await this._ws({ type: "wand/device/update", entity_id: entityId, x: 0.5, y: 0.5, enabled: true });
        break;
      }
      case "toggle-enabled":
        await this._ws({ type: "wand/device/update", entity_id: dialog.id, enabled: ev.target.checked });
        break;
      case "remove-device":
        this._dialog = null;
        await this._ws({ type: "wand/device/remove", entity_id: dialog.id });
        break;
      case "more-info":
        this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: dialog.id }, bubbles: true, composed: true }));
        break;
      case "add-spot": {
        const spots = [...(this._config.spots || [])];
        const id = `spot_${Date.now().toString(36)}`;
        spots.push({ id, name: `Spot ${spots.length + 1}`, x: 0.5, y: 0.5 });
        this._dialog = { kind: "spot", id };
        await this._ws({ type: "wand/spots/set", spots });
        break;
      }
      case "save-spot": {
        const name = this.shadowRoot.querySelector("[data-field='spot-name']").value.trim() || "Spot";
        const spots = this._config.spots.map((s) => (s.id === dialog.id ? { ...s, name } : s));
        this._dialog = null;
        await this._ws({ type: "wand/spots/set", spots });
        break;
      }
      case "remove-spot": {
        const spots = this._config.spots.filter((s) => s.id !== dialog.id);
        this._dialog = null;
        await this._ws({ type: "wand/spots/set", spots });
        break;
      }
      case "save-spellbook":
        await this._saveSpellbook();
        break;
      default:
        break;
    }
  }

  async _saveDeviceSpells() {
    const entityId = this._dialog.id;
    const checked = [...this.shadowRoot.querySelectorAll("[data-spell]")]
      .filter((el) => el.checked)
      .map((el) => el.getAttribute("data-spell"));
    const all = this._spellsFor(entityId).map((s) => s.id);
    const spells = checked.length === all.length ? null : checked;
    await this._ws({ type: "wand/device/update", entity_id: entityId, spells });
  }

  async _saveSpellbook() {
    const inputs = [...this.shadowRoot.querySelectorAll("[data-words]")];
    for (const input of inputs) {
      const spellId = input.getAttribute("data-words");
      const words = input.value.split(",").map((w) => w.trim()).filter(Boolean);
      const current = this._config.spells.find((s) => s.id === spellId)?.words || [];
      if (words.join("|") === current.join("|")) continue;
      try {
        this._config = await this._hass.callWS({ type: "wand/spell/words", spell_id: spellId, words });
      } catch (err) {
        this._error = err?.message || "Couldn't save the spellbook";
      }
    }
    this._dialog = null;
    this._render();
  }

  async _upload(file) {
    if (!file) return;
    const aspect = await new Promise((resolve) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        resolve(img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : null);
        URL.revokeObjectURL(url);
      };
      img.onerror = () => {
        resolve(null);
        URL.revokeObjectURL(url);
      };
      img.src = url;
    });
    const form = new FormData();
    form.append("file", file, file.name);
    const query = aspect ? `?aspect=${aspect.toFixed(5)}` : "";
    const response = await this._hass.fetchWithAuth(`/api/wand/floorplan${query}`, { method: "POST", body: form });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      this._error = body.message || "Upload failed";
      this._render();
      return;
    }
    this._imageAspect = aspect;
    await this._load();
  }

  _bindDrag(el, kind) {
    el.addEventListener("pointerdown", (down) => {
      const plan = this.shadowRoot.querySelector(".plan");
      const startX = down.clientX;
      const startY = down.clientY;
      let moved = false;
      const canDrag = this._edit && this._isAdmin;
      if (canDrag) el.setPointerCapture(down.pointerId);

      const onMove = (ev) => {
        if (!canDrag) return;
        if (Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 4) moved = true;
        if (!moved) return;
        const rect = plan.getBoundingClientRect();
        const x = Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width));
        const y = Math.min(1, Math.max(0, (ev.clientY - rect.top) / rect.height));
        el.style.left = `${x * 100}%`;
        el.style.top = `${y * 100}%`;
        el.dataset.x = x;
        el.dataset.y = y;
      };
      const onUp = async () => {
        el.removeEventListener("pointermove", onMove);
        el.removeEventListener("pointerup", onUp);
        if (!moved) {
          if (kind === "entity") this._open({ kind: "device", id: el.getAttribute("data-entity") });
          else if (this._edit) this._open({ kind: "spot", id: el.getAttribute("data-spot") });
          return;
        }
        const x = Number(el.dataset.x);
        const y = Number(el.dataset.y);
        if (kind === "entity") {
          await this._ws({ type: "wand/device/update", entity_id: el.getAttribute("data-entity"), x, y });
        } else {
          const spots = this._config.spots.map((s) => (s.id === el.getAttribute("data-spot") ? { ...s, x, y } : s));
          await this._ws({ type: "wand/spots/set", spots });
        }
      };
      el.addEventListener("pointermove", onMove);
      el.addEventListener("pointerup", onUp);
    });
  }
}

const STYLES = `
  :host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  .toolbar { display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 16px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, white); }
  .title { font-size: 20px; }
  .spacer { flex: 1; }
  .content { max-width: 960px; margin: 0 auto; padding: 16px; display: grid; gap: 16px; }
  .card { background: var(--card-background-color); border-radius: var(--ha-card-border-radius, 12px); border: 1px solid var(--divider-color); padding: 12px; }
  .btn { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); border-radius: 18px; padding: 6px 14px; font: inherit; font-size: 14px; cursor: pointer; }
  .toolbar .btn { background: transparent; color: inherit; border-color: rgba(255,255,255,0.4); }
  .btn.on, .btn.primary { background: var(--primary-color); color: var(--text-primary-color, white); border-color: var(--primary-color); }
  .btn.danger { color: var(--error-color); }
  .btn[disabled] { opacity: 0.5; cursor: default; }
  .btn ha-icon { --mdc-icon-size: 18px; }
  .editbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .hint, .sub { color: var(--secondary-text-color); font-size: 13px; }
  .error { color: var(--error-color); }
  .plan { position: relative; margin: 0 auto; touch-action: none; user-select: none; background: var(--secondary-background-color); border-radius: 8px; overflow: hidden; }
  .plan img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: fill; }
  .plan.editing { outline: 2px dashed var(--primary-color); outline-offset: -2px; }
  .empty { position: absolute; inset: 0; display: grid; place-items: center; color: var(--secondary-text-color); padding: 24px; text-align: center; }
  .marker { position: absolute; width: 36px; height: 36px; margin: -18px 0 0 -18px; border-radius: 50%; display: grid; place-items: center; cursor: pointer; background: var(--card-background-color); border: 2px solid var(--primary-color); color: var(--primary-color); box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
  .marker.active { color: var(--state-light-active-color, #ffb300); border-color: var(--state-light-active-color, #ffb300); }
  .marker.blocked { border-color: var(--disabled-text-color, #999); color: var(--disabled-text-color, #999); opacity: 0.75; }
  .marker .slash { position: absolute; width: 40px; height: 2px; background: var(--disabled-text-color, #999); transform: rotate(-45deg); }
  .plan.editing .marker, .plan.editing .spot { cursor: grab; }
  .marker ha-icon { --mdc-icon-size: 20px; }
  .spot { position: absolute; transform: translate(-50%, -50%); display: flex; align-items: center; gap: 4px; padding: 2px 8px 2px 4px; border-radius: 12px; background: var(--primary-color); color: var(--text-primary-color, white); font-size: 12px; cursor: default; white-space: nowrap; }
  .spot ha-icon { --mdc-icon-size: 16px; }
  .list { display: grid; gap: 2px; }
  .list-head { padding: 4px 4px 8px; }
  .row { display: flex; align-items: center; gap: 12px; padding: 8px 4px; border-radius: 8px; cursor: pointer; }
  .row:hover { background: var(--secondary-background-color); }
  .row ha-icon { color: var(--primary-color); }
  .row.active ha-icon:first-child { color: var(--state-light-active-color, #ffb300); }
  .row.muted { opacity: 0.55; }
  .row-text { flex: 1; min-width: 0; }
  .row .sub { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chev { color: var(--secondary-text-color) !important; }
  .scrim { position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 10; }
  .dialog { position: fixed; z-index: 11; left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(440px, calc(100vw - 32px)); max-height: calc(100vh - 64px); overflow: auto; background: var(--card-background-color); border-radius: 16px; padding: 20px; display: grid; gap: 12px; box-sizing: border-box; }
  .dialog-head { display: flex; align-items: center; gap: 12px; }
  .dialog-head ha-icon { color: var(--primary-color); }
  .dialog-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .switch-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
  .section-title { font-weight: 500; }
  .spells { display: grid; gap: 4px; }
  .spell { display: grid; grid-template-columns: auto auto 1fr; gap: 8px; align-items: center; }
  .spell.muted { opacity: 0.5; }
  .field { display: grid; gap: 4px; font-size: 14px; }
  .field input, .field select { font: inherit; padding: 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--secondary-background-color); color: var(--primary-text-color); }
  input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--primary-color); }
`;

customElements.define("wand-panel", WandPanel);

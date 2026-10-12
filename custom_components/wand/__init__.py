"""The Wand integration: point a watch at a device and cast a spell."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant

from . import websocket
from .api import WandCastView, WandConfigView, WandFloorplanView
from .caster import async_cast
from .const import (
    DOMAIN,
    EVENT_LEGACY_SPELL,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL,
)
from .store import WandStore

FRONTEND_DIR = Path(__file__).parent / "frontend"
REGISTERED = f"{DOMAIN}_http_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = WandStore(hass)
    await store.async_load()
    hass.data[DOMAIN] = store

    # HTTP views, static files and WebSocket commands can't be unregistered,
    # so they're added once per Home Assistant run and look up the store live.
    if not hass.data.get(REGISTERED):
        hass.http.register_view(WandConfigView())
        hass.http.register_view(WandCastView())
        hass.http.register_view(WandFloorplanView())
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        websocket.async_register(hass)
        hass.data[REGISTERED] = True

    version = entry.entry_id[:8]
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="wand-panel",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/wand-panel.js?v={version}",
        require_admin=False,
        config={},
    )

    async def _legacy_spell(event: Event) -> None:
        """Casts fired as events by early versions of the watch app."""
        entity_id = event.data.get("entity_id")
        spell = event.data.get("spell")
        if isinstance(entity_id, str) and isinstance(spell, str):
            await async_cast(hass, store, entity_id, spell, event.context)

    entry.async_on_unload(hass.bus.async_listen(EVENT_LEGACY_SPELL, _legacy_spell))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    hass.data.pop(DOMAIN, None)
    return True

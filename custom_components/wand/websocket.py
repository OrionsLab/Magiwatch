"""WebSocket commands used by the floor-plan page."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SUPPORTED_DOMAINS
from .spells import SPELLS, SPELLS_BY_ID
from .store import WandStore

COORD = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_update_device)
    websocket_api.async_register_command(hass, ws_remove_device)
    websocket_api.async_register_command(hass, ws_set_spell_words)
    websocket_api.async_register_command(hass, ws_set_spots)


def _store(hass: HomeAssistant) -> WandStore:
    return hass.data[DOMAIN]


def _full_config(store: WandStore) -> dict[str, Any]:
    return {
        "devices": store.data["devices"],
        "spots": store.data["spots"],
        "floorplan": store.data["floorplan"],
        "supported_domains": list(SUPPORTED_DOMAINS),
        "spells": [
            {
                "id": s.id,
                "name": s.name,
                "words": store.spell_words(s.id),
                "gesture": s.gesture,
                "domains": sorted(s.effects),
            }
            for s in SPELLS
        ],
    }


@websocket_api.websocket_command({vol.Required("type"): "wand/config"})
@callback
def ws_get_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    connection.send_result(msg["id"], _full_config(_store(hass)))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "wand/device/update",
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("x"): COORD,
        vol.Optional("y"): COORD,
        vol.Optional("enabled"): bool,
        vol.Optional("spells"): vol.Any(None, [vol.In(list(SPELLS_BY_ID))]),
    }
)
@websocket_api.async_response
async def ws_update_device(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if msg["entity_id"].split(".")[0] not in SUPPORTED_DOMAINS:
        connection.send_error(msg["id"], "unsupported_domain", "The wand can't control this kind of device")
        return
    changes = {k: msg[k] for k in ("x", "y", "enabled", "spells") if k in msg}
    store = _store(hass)
    await store.async_update_device(msg["entity_id"], changes)
    connection.send_result(msg["id"], _full_config(store))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "wand/device/remove", vol.Required("entity_id"): cv.entity_id}
)
@websocket_api.async_response
async def ws_remove_device(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    store = _store(hass)
    await store.async_remove_device(msg["entity_id"])
    connection.send_result(msg["id"], _full_config(store))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "wand/spell/words",
        vol.Required("spell_id"): vol.In([s.id for s in SPELLS if not s.gesture]),
        vol.Required("words"): [vol.All(str, vol.Length(min=1, max=40))],
    }
)
@websocket_api.async_response
async def ws_set_spell_words(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    store = _store(hass)
    await store.async_set_spell_words(msg["spell_id"], msg["words"])
    connection.send_result(msg["id"], _full_config(store))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "wand/spots/set",
        vol.Required("spots"): [
            {
                vol.Required("id"): vol.All(str, vol.Length(min=1, max=40)),
                vol.Required("name"): vol.All(str, vol.Length(min=1, max=40)),
                vol.Required("x"): COORD,
                vol.Required("y"): COORD,
            }
        ],
    }
)
@websocket_api.async_response
async def ws_set_spots(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    store = _store(hass)
    await store.async_set_spots(msg["spots"])
    connection.send_result(msg["id"], _full_config(store))

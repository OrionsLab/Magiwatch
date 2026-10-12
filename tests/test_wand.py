"""Tests for the Wand integration."""

from http import HTTPStatus

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.wand.const import DOMAIN


@pytest.fixture
async def wand(hass: HomeAssistant):
    assert await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set("light.lamp", "off", {"friendly_name": "Lamp"})
    hass.states.async_set("media_player.tv", "playing", {"friendly_name": "TV"})
    return entry


async def test_panel_registered(hass, wand):
    assert "wand" in hass.data["frontend_panels"]


async def test_place_device_and_watch_config(hass, wand, hass_ws_client, hass_client):
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/device/update", "entity_id": "light.lamp", "x": 0.3, "y": 0.2, "enabled": True})
    msg = await ws.receive_json()
    assert msg["success"], msg
    assert msg["result"]["devices"]["light.lamp"]["x"] == 0.3

    await ws.send_json({"id": 2, "type": "wand/device/update", "entity_id": "media_player.tv", "enabled": False})
    assert (await ws.receive_json())["success"]

    client = await hass_client()
    resp = await client.get("/api/wand/config")
    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert [d["entity_id"] for d in body["devices"]] == ["light.lamp"]
    lamp = body["devices"][0]
    assert lamp["name"] == "Lamp"
    assert "lumos" in lamp["spells"] and "silencio" not in lamp["spells"]
    assert {"id": "lumos", "name": "Lumos", "words": ["lumos"], "gesture": False} in body["spells"]


async def test_cast_allowed_and_denied(hass, wand, hass_ws_client, hass_client):
    turn_on = async_mock_service(hass, "homeassistant", "turn_on")
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/device/update", "entity_id": "light.lamp", "enabled": True})
    await ws.receive_json()
    await ws.send_json({"id": 2, "type": "wand/device/update", "entity_id": "media_player.tv", "enabled": False})
    await ws.receive_json()

    client = await hass_client()
    resp = await client.post("/api/wand/cast", json={"entity_id": "light.lamp", "spell": "lumos"})
    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {"ok": True, "action": "homeassistant.turn_on"}
    assert turn_on[0].data == {"entity_id": "light.lamp"}

    resp = await client.post("/api/wand/cast", json={"entity_id": "media_player.tv", "spell": "lumos"})
    assert resp.status == HTTPStatus.FORBIDDEN
    assert (await resp.json())["error"] == "not_allowed"

    resp = await client.post("/api/wand/cast", json={"entity_id": "light.lamp", "spell": "silencio"})
    assert resp.status == HTTPStatus.BAD_REQUEST
    assert (await resp.json())["error"] == "unsupported"

    resp = await client.post("/api/wand/cast", json={"entity_id": "light.lamp", "spell": "avada"})
    assert (await resp.json())["error"] == "unknown_spell"


async def test_input_boolean_lumos_nox(hass, wand, hass_ws_client, hass_client):
    turn_off = async_mock_service(hass, "homeassistant", "turn_off")
    hass.states.async_set("input_boolean.away", "on", {"friendly_name": "Away"})
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/device/update", "entity_id": "input_boolean.away", "enabled": True})
    assert (await ws.receive_json())["success"]

    client = await hass_client()
    resp = await client.post("/api/wand/cast", json={"entity_id": "input_boolean.away", "spell": "nox"})
    assert await resp.json() == {"ok": True, "action": "homeassistant.turn_off"}
    assert turn_off[0].data == {"entity_id": "input_boolean.away"}


async def test_per_device_spell_limits(hass, wand, hass_ws_client, hass_client):
    async_mock_service(hass, "light", "turn_on")
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/device/update", "entity_id": "light.lamp", "enabled": True, "spells": ["lumos", "nox"]})
    assert (await ws.receive_json())["success"]

    client = await hass_client()
    resp = await client.post("/api/wand/cast", json={"entity_id": "light.lamp", "spell": "lumos_maxima"})
    assert resp.status == HTTPStatus.FORBIDDEN


async def test_spell_words_editable(hass, wand, hass_ws_client, hass_client):
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/spell/words", "spell_id": "lumos", "words": ["Lumos", " light up "]})
    msg = await ws.receive_json()
    assert msg["success"]
    lumos = next(s for s in msg["result"]["spells"] if s["id"] == "lumos")
    assert lumos["words"] == ["lumos", "light up"]


async def test_finite_turns_off_area(hass, wand, hass_ws_client, hass_client):
    turn_off = async_mock_service(hass, "homeassistant", "turn_off")
    area = ar.async_get(hass).async_create("Living room")
    entry = er.async_get(hass).async_get_or_create("light", "test", "desk1", suggested_object_id="desk")
    er.async_get(hass).async_update_entity(entry.entity_id, area_id=area.id)

    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/device/update", "entity_id": entry.entity_id, "enabled": True})
    await ws.receive_json()
    client = await hass_client()
    resp = await client.post("/api/wand/cast", json={"entity_id": entry.entity_id, "spell": "finite"})
    assert resp.status == HTTPStatus.OK
    assert turn_off[0].data == {"area_id": area.id}


async def test_legacy_event(hass, wand, hass_ws_client):
    turn_off = async_mock_service(hass, "homeassistant", "turn_off")
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "wand/device/update", "entity_id": "light.lamp", "enabled": True})
    await ws.receive_json()
    hass.bus.async_fire("wand_spell", {"entity_id": "light.lamp", "spell": "nox"})
    await hass.async_block_till_done()
    assert turn_off[0].data == {"entity_id": "light.lamp"}


async def test_floorplan_upload_and_get(hass, wand, hass_client):
    client = await hass_client()
    import aiohttp

    form = aiohttp.FormData()
    form.add_field("file", b"\x89PNG\r\n\x1a\nfake", filename="plan.png", content_type="image/png")
    resp = await client.post("/api/wand/floorplan?aspect=0.6", data=form)
    assert resp.status == HTTPStatus.OK, await resp.text()
    resp = await client.get("/api/wand/floorplan")
    assert resp.status == HTTPStatus.OK
    assert (await resp.read()).startswith(b"\x89PNG")
    assert hass.data[DOMAIN].data["floorplan"] == {"filename": "floorplan.png", "aspect": 0.6}


async def test_unload(hass, wand):
    assert await hass.config_entries.async_unload(wand.entry_id)
    assert "wand" not in hass.data.get("frontend_panels", {})

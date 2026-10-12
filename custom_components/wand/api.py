"""HTTP API used by the watch app and by the floor-plan page."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import KEY_HASS_USER, HomeAssistantView
from homeassistant.core import HomeAssistant

from .caster import async_cast
from .const import DOMAIN, FLOORPLAN_DIR, FLOORPLAN_MAX_BYTES, FLOORPLAN_TYPES
from .spells import SPELLS
from .store import WandStore


def _store(hass: HomeAssistant) -> WandStore | None:
    return hass.data.get(DOMAIN)


def watch_config(hass: HomeAssistant, store: WandStore) -> dict[str, Any]:
    """The allowed devices and spell words, in the shape the watch app reads."""
    devices = []
    for entity_id, device in store.data["devices"].items():
        if not device.get("enabled"):
            continue
        state = hass.states.get(entity_id)
        devices.append(
            {
                "entity_id": entity_id,
                "name": state.name if state else entity_id,
                "domain": entity_id.split(".")[0],
                "x": device["x"],
                "y": device["y"],
                "spells": store.allowed_spells(entity_id),
            }
        )
    return {
        "version": 1,
        "devices": devices,
        "spells": [
            {"id": s.id, "name": s.name, "words": store.spell_words(s.id), "gesture": s.gesture}
            for s in SPELLS
        ],
        "spots": store.data["spots"],
    }


class WandConfigView(HomeAssistantView):
    """GET /api/wand/config: what the watch may control."""

    url = "/api/wand/config"
    name = "api:wand:config"

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        if (store := _store(hass)) is None:
            return self.json_message("Wand is not set up", HTTPStatus.NOT_FOUND)
        return self.json(watch_config(hass, store))


class WandCastView(HomeAssistantView):
    """POST /api/wand/cast {"entity_id", "spell"}: cast a spell on a device."""

    url = "/api/wand/cast"
    name = "api:wand:cast"

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        if (store := _store(hass)) is None:
            return self.json_message("Wand is not set up", HTTPStatus.NOT_FOUND)
        try:
            body = await request.json()
            entity_id = str(body["entity_id"])
            spell = str(body["spell"])
        except (ValueError, KeyError, TypeError):
            return self.json({"ok": False, "error": "bad_request"}, HTTPStatus.BAD_REQUEST)

        result = await async_cast(hass, store, entity_id, spell, self.context(request))
        status = HTTPStatus.OK
        if result.error in ("not_allowed",):
            status = HTTPStatus.FORBIDDEN
        elif result.error:
            status = HTTPStatus.BAD_REQUEST
        return self.json(result.as_dict(), status)


class WandFloorplanView(HomeAssistantView):
    """GET or POST (admin) the floor-plan image."""

    url = "/api/wand/floorplan"
    name = "api:wand:floorplan"

    async def get(self, request: web.Request) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        store = _store(hass)
        filename = store.data["floorplan"]["filename"] if store else None
        if not filename:
            return self.json_message("No floor plan", HTTPStatus.NOT_FOUND)
        path = Path(hass.config.path(FLOORPLAN_DIR, filename))
        if not await hass.async_add_executor_job(path.is_file):
            return self.json_message("No floor plan", HTTPStatus.NOT_FOUND)
        return web.FileResponse(path, headers={"Cache-Control": "no-store"})

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        if not request[KEY_HASS_USER].is_admin:
            return self.json_message("Admin only", HTTPStatus.UNAUTHORIZED)
        if (store := _store(hass)) is None:
            return self.json_message("Wand is not set up", HTTPStatus.NOT_FOUND)

        reader = await request.multipart()
        field = await reader.next()
        if field is None or field.name != "file":
            return self.json_message("Expected a 'file' field", HTTPStatus.BAD_REQUEST)
        content_type = (field.headers.get("Content-Type") or "").split(";")[0].strip()
        extension = FLOORPLAN_TYPES.get(content_type)
        if extension is None:
            return self.json_message("Use a PNG, JPEG, WebP or SVG image", HTTPStatus.BAD_REQUEST)

        chunks: list[bytes] = []
        size = 0
        while chunk := await field.read_chunk():
            size += len(chunk)
            if size > FLOORPLAN_MAX_BYTES:
                return self.json_message("Image is larger than 10 MB", HTTPStatus.BAD_REQUEST)
            chunks.append(chunk)

        try:
            aspect = float(request.query.get("aspect", ""))
        except ValueError:
            aspect = None

        filename = f"floorplan.{extension}"

        def _write() -> None:
            folder = Path(hass.config.path(FLOORPLAN_DIR))
            folder.mkdir(exist_ok=True)
            for old in folder.glob("floorplan.*"):
                old.unlink()
            (folder / filename).write_bytes(b"".join(chunks))

        await hass.async_add_executor_job(_write)
        await store.async_set_floorplan(filename, aspect)
        return self.json({"ok": True, "filename": filename})

"""Turn a cast (device + spell) into a Home Assistant service call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.const import ATTR_AREA_ID, ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers import device_registry as dr

from .const import EVENT_CAST
from .spells import SPELLS_BY_ID
from .store import WandStore


@dataclass
class CastResult:
    """Outcome of a cast, also returned to the watch."""

    ok: bool
    error: str | None = None
    action: str | None = None

    def as_dict(self) -> dict[str, Any]:
        if self.ok:
            return {"ok": True, "action": self.action}
        return {"ok": False, "error": self.error}


def _area_of(hass: HomeAssistant, entity_id: str) -> str | None:
    entry = er.async_get(hass).async_get(entity_id)
    if entry is None:
        return None
    if entry.area_id:
        return entry.area_id
    if entry.device_id and (device := dr.async_get(hass).async_get(entry.device_id)):
        return device.area_id
    return None


async def async_cast(
    hass: HomeAssistant,
    store: WandStore,
    entity_id: str,
    spell_id: str,
    context: Context | None = None,
) -> CastResult:
    """Run a spell on a device if the Wand configuration allows it."""
    spell = SPELLS_BY_ID.get(spell_id)
    if spell is None:
        return CastResult(False, "unknown_spell")
    device = store.device(entity_id)
    if device is None or not device.get("enabled"):
        return CastResult(False, "not_allowed")
    effect = spell.effect_for(entity_id.split(".")[0])
    if effect is None:
        return CastResult(False, "unsupported")
    if spell_id not in store.allowed_spells(entity_id):
        return CastResult(False, "not_allowed")

    if effect.target == "area":
        area_id = _area_of(hass, entity_id)
        if area_id is None or ar.async_get(hass).async_get_area(area_id) is None:
            return CastResult(False, "no_area")
        target = {ATTR_AREA_ID: area_id}
    else:
        target = {ATTR_ENTITY_ID: entity_id}

    await hass.services.async_call(
        effect.domain,
        effect.service,
        {**effect.data, **target},
        blocking=True,
        context=context,
    )
    action = f"{effect.domain}.{effect.service}"
    hass.bus.async_fire(
        EVENT_CAST,
        {"entity_id": entity_id, "spell": spell_id, "action": action},
        context=context,
    )
    return CastResult(True, action=action)

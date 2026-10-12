"""Persistent Wand configuration: floor plan, placed devices, spell words, casting spots."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .spells import SPELLS, SPELLS_BY_ID

DEFAULT_DATA: dict[str, Any] = {
    # entity_id -> {"x": 0..1, "y": 0..1, "enabled": bool, "spells": [ids] | None}
    # "spells": None means every spell that works on the device's domain.
    "devices": {},
    # spell_id -> spoken words; missing means the catalog default.
    "spell_words": {},
    # [{"id", "name", "x", "y"}]
    "spots": [],
    # {"filename": str | None, "aspect": width / height | None}
    "floorplan": {"filename": None, "aspect": None},
}


class WandStore:
    """Load, change and save the Wand configuration."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = copy.deepcopy(DEFAULT_DATA)

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            for key, value in stored.items():
                if key in self.data:
                    self.data[key] = value

    async def async_save(self) -> None:
        await self._store.async_save(self.data)

    # Devices

    def device(self, entity_id: str) -> dict[str, Any] | None:
        return self.data["devices"].get(entity_id)

    async def async_update_device(self, entity_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        device = self.data["devices"].setdefault(
            entity_id, {"x": 0.5, "y": 0.5, "enabled": True, "spells": None}
        )
        device.update(changes)
        await self.async_save()
        return device

    async def async_remove_device(self, entity_id: str) -> None:
        self.data["devices"].pop(entity_id, None)
        await self.async_save()

    def allowed_spells(self, entity_id: str) -> list[str]:
        """Spell ids this device accepts, given its domain and its settings."""
        device = self.device(entity_id)
        if not device or not device.get("enabled"):
            return []
        domain = entity_id.split(".")[0]
        chosen = device.get("spells")
        return [
            spell.id
            for spell in SPELLS
            if spell.supports(domain) and (chosen is None or spell.id in chosen)
        ]

    # Spells

    def spell_words(self, spell_id: str) -> list[str]:
        words = self.data["spell_words"].get(spell_id)
        if words is None:
            return list(SPELLS_BY_ID[spell_id].words)
        return list(words)

    async def async_set_spell_words(self, spell_id: str, words: list[str]) -> None:
        cleaned = [w.strip().lower() for w in words if w.strip()]
        self.data["spell_words"][spell_id] = cleaned
        await self.async_save()

    # Spots and floor plan

    async def async_set_spots(self, spots: list[dict[str, Any]]) -> None:
        self.data["spots"] = spots
        await self.async_save()

    async def async_set_floorplan(self, filename: str | None, aspect: float | None) -> None:
        self.data["floorplan"] = {"filename": filename, "aspect": aspect}
        await self.async_save()

"""Spell catalog: what each spell does on each kind of device."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ANY = "*"


@dataclass(frozen=True)
class Effect:
    """One service call a spell makes on a device."""

    domain: str
    service: str
    data: dict[str, Any] = field(default_factory=dict)
    # "entity" targets the pointed device, "area" targets its whole area.
    target: str = "entity"


@dataclass(frozen=True)
class Spell:
    """A spell or gesture the wand can cast."""

    id: str
    name: str
    words: tuple[str, ...]
    effects: dict[str, Effect]
    gesture: bool = False

    def effect_for(self, domain: str) -> Effect | None:
        """Return the effect on a device of this domain, if any."""
        return self.effects.get(domain) or self.effects.get(ANY)

    def supports(self, domain: str) -> bool:
        """Whether the spell does anything on this domain."""
        return self.effect_for(domain) is not None


SPELLS: tuple[Spell, ...] = (
    Spell("lumos", "Lumos", ("lumos",),
          {ANY: Effect("homeassistant", "turn_on")}),
    Spell("nox", "Nox", ("nox",),
          {ANY: Effect("homeassistant", "turn_off")}),
    Spell("lumos_maxima", "Lumos Maxima", ("lumos maxima",),
          {"light": Effect("light", "turn_on", {"brightness_pct": 100})}),
    Spell("incendio", "Incendio", ("incendio",), {
        "light": Effect("light", "turn_on", {"color_temp_kelvin": 2700}),
        "climate": Effect("climate", "set_hvac_mode", {"hvac_mode": "heat"}),
    }),
    Spell("glacius", "Glacius", ("glacius",), {
        "light": Effect("light", "turn_on", {"color_temp_kelvin": 6000}),
        "climate": Effect("climate", "set_hvac_mode", {"hvac_mode": "cool"}),
    }),
    Spell("silencio", "Silencio", ("silencio",), {
        "media_player": Effect("media_player", "volume_mute", {"is_volume_muted": True}),
    }),
    Spell("sonorus", "Sonorus", ("sonorus",), {
        "media_player": Effect("media_player", "volume_up"),
    }),
    # Locks are deliberately not supported: a spoken word should not unlock a door.
    Spell("alohomora", "Alohomora", ("alohomora",), {
        "cover": Effect("cover", "open_cover"),
    }),
    Spell("colloportus", "Colloportus", ("colloportus",), {
        "cover": Effect("cover", "close_cover"),
    }),
    Spell("finite", "Finite", ("finite",),
          {ANY: Effect("homeassistant", "turn_off", target="area")}),
    Spell("flick_up", "Flick up", (), {
        "light": Effect("light", "turn_on", {"brightness_step_pct": 10}),
        "media_player": Effect("media_player", "volume_up"),
    }, gesture=True),
    Spell("flick_down", "Flick down", (), {
        "light": Effect("light", "turn_on", {"brightness_step_pct": -10}),
        "media_player": Effect("media_player", "volume_down"),
    }, gesture=True),
)

SPELLS_BY_ID: dict[str, Spell] = {spell.id: spell for spell in SPELLS}

# Magiwatch

Point your watch at a device, say a spell, and Home Assistant does it.

This repository is the **Wand** integration for Home Assistant, installable through HACS. It gives you a floor plan of your home with the devices the wand may control, the spells each device accepts, and the words you say for each spell. The Magiwatch watch app talks to it through the API below.

## Install the integration

1. In HACS, open the menu, choose **Custom repositories**, add `https://github.com/OrionsLab/Magiwatch` as type **Integration**, then download **Wand**.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and pick **Wand**.

A **Wand** page appears in the sidebar.

## Set it up

1. On the Wand page, click **Edit**, then **Upload floor plan** (PNG, JPEG, WebP or SVG, up to 10 MB).
2. Click **Add device** for each device the wand should know about, then drag its icon to where it is on the plan.
3. Click an icon to choose whether the wand may control it and which spells it accepts.
4. Click **Add casting spot** to mark where you usually stand when you cast (for example the sofa).
5. Open **Spellbook** to change the words for each spell. Separate alternatives with commas.

Devices that aren't allowed are shown greyed out with a slash, and the list under the plan shows at a glance what the wand can control.

## Spells

| Spell | Does | Works on |
| --- | --- | --- |
| Lumos | Turn on | Everything |
| Nox | Turn off | Everything |
| Lumos Maxima | Full brightness | Lights |
| Incendio | Warm white / heat | Lights, climate |
| Glacius | Cool white / cool | Lights, climate |
| Silencio | Mute | Media players |
| Sonorus | Volume up | Media players |
| Alohomora | Open | Covers |
| Colloportus | Close | Covers |
| Finite | Turn off everything in the device's area | Everything in an area |
| Flick up / down (gesture) | One step brighter / louder, or dimmer / quieter | Lights, media players |

Locks are not supported on purpose: a spoken word should not unlock a door.

Every successful cast fires a `wand_cast` event (`entity_id`, `spell`, `action`) that your own automations can use.

## API for the watch app

All calls use a Home Assistant long-lived access token (`Authorization: Bearer <token>`).

- `GET /api/wand/config` returns the allowed devices (with plan coordinates and accepted spells), the spells with their words, and the casting spots.
- `POST /api/wand/cast` with `{"entity_id": "light.lamp", "spell": "lumos"}` returns `{"ok": true, "action": "homeassistant.turn_on"}`, or `{"ok": false, "error": "not_allowed" | "unsupported" | "unknown_spell" | "no_area"}`.

## Development

```
pip install pytest-homeassistant-custom-component
pytest
```

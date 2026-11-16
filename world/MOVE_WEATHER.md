# Authored local move weather (experimental)

Independent stack on app #419/native #78, not Maya's #410/#72 or released RC12.
Vanilla remains the default. Start the development client with the existing
`--experimental-field-moves` option and the paired native build.

An actor can discover `move_weather.maps` and use `world.configure_move_weather`
with a reviewed route, the existing move-selector JSON, `weather` (`rain`, `sun`,
`sandstorm`), `frames` (600..3600), and `pp` (1..4). The profile is durable and
actor-owned. Authoring commits configuration, never weather activation or an
encounter. The actor does not spend a player's PP or activate weather remotely.

In the actual party WORLD MOVE UI, choose a learned move, then explicitly request
an authored weather profile. This lookup sends that move ID to the authenticated
world host. The response does not activate anything. A separate choice displays
the local weather, PP cost and duration; its default is **other interactions**.
Native rechecks the actual conscious non-egg source, learned move, PP and location.

## Effects and limits

- This is LOCAL weather, not shared climate. Native weather transitions provide
  the existing rain, drought/sun or sandstorm field effects. Actual stock initial
  battle weather and weather-dependent party forms apply; it is not cosmetic.
- Only stable clear weather (`NONE` or `SUNNY`) matching both the saved weather
  and map header is eligible. Saved rain, abnormal/cycling weather, transitions,
  generated places, Safari and facilities are excluded. A listed route can still
  be unavailable under the player's actual story/weather state.
- A profile requests a stock transition. A battle entered before that transition
  completes can inherit the previous weather, not the requested weather.
- Duration is native weather-task ticks, not wall-clock seconds. Battles pause it.
  At expiry or connection loss the baseline is restored through stock cleanup;
  the getter reports the baseline during cleanup to avoid leaking an expired
  overlay into a new battle. Native story/map weather setters supersede the lease.
- No saved-weather writes, save-layout changes or forced save. PP is an ordinary
  native mutation and is saved normally. Stock weather-form transitions still
  modify party forms using the engine's normal rules. Restart loads ordinary
  saved weather, not the expired runtime lease.
- Existing co-op captures the initiator's actual current weather and distributes
  that battle snapshot. This implementation does not change that protocol or
  other players' overworld climate. Linked PvP and recorded battles do not use
  this player's private overlay. Thunderstorm/fog terrain effects are excluded.
- No climate history, activation report, NPC weather knowledge, weather reward,
  captured individual or victory is fabricated.

## Verification and remaining QA

Component tests compile the real native controller and UI against fixture engine
APIs, covering default-off, actual learned move/PP guard, explicit consent,
expiry, external weather priority, disconnect reset, map/save identity isolation,
PvP exclusion and co-op getter behavior. App tests execute real actor plans,
durable configuration reload, ownership/bounds and authenticated fresh presence.
These are not a full linked-engine or multiplayer playtest. Rendered transition,
Castform/Cherrim form restoration, saving/loading during a transition, story
weather interruption, and paired co-op initialization remain mandatory QA before
promoting this experimental path. No live model/provider was used.

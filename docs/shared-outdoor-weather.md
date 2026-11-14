# Shared agent-authored outdoor weather

`world.set_weather(revision, mode)` gives the author a general environmental
primitive on the actual active, archived 127x127 outdoor destination that its
world-owned actor occupies. Modes are clear, clouds, rain, snow, fog, overcast and
default. No named scenario, forecast, character power, rainfall simulation or
new biome art is inferred. This does not open additional outdoor regions.

The authority persists the mode under the immutable destination revision and
commits its change to public history. Observation returns the setting separately
from sensed geometry. Agents may combine committed events, waits, observation and
their own plans to decide when to change it. No fixed cycle is imposed.

WEATHER1 clients receive a setting only while on that exact destination after its
geometry ACK. Native uses Expansion's existing SetNextWeather transition. It waits
for a ready field and a completed previous transition; never changes weather during
battle, menus, scripts or warps. Rain/snow/fog use native effects, including normal
battle/weather and form behavior where the engine implements them. No direct party,
save weather, badge or legendary-story flag writes are added.

The native adapter remembers the map's prior weather and restores it after removal,
stale connection, disable or disconnect when safely back in the same field. If the
player has left for another map, that map's existing initialization owns weather:
the adapter drops its lease and never overwrites Hoenn's weather. Changing exact
destination identity invalidates the old setting. Old clients receive no weather
frame and retain their usual map weather; synchronization therefore requires capable
clients, and is not frame-exact across players busy in battles or menus.

This is only the currently supported shared format-16 outdoor destination. Indoor
caves, original Hoenn, severe drought/legendary abnormal weather and the uncertain
multi-outdoor REGION operation are excluded.

Tests run actual authority plan/snapshot through actual C parser/weather-pump logic
with engine fixtures, including waiting through busy states, restoration, wrong map,
missing ACK, unsupported clients and persistence. They are not rendered weather or
linked battle/form/save QA. Maya should verify weather transition graphics/audio,
native battle effects/forms, save/reload, map exits and two-client behavior before
integration/release. No live model calls or client-application success are claimed.

Paired native draft #39: 25c767033ae3125611ec1405658a58b807190635.

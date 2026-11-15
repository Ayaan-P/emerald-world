# Character-led field reconnaissance

A rendered generated-world character can independently measure route access while
travelling. Add `survey: "Northern access transect"` to an ordinary history-backed
`character_actions` journey. The title is literal public text (1–48 characters).
No player survey session, expedition acceptance, or player work is involved.

The authority executes the existing cardinal journey, including occupancy waits,
segment transitions and restart recovery. Only its actual completed journey
produces a `character_field_report`, atomically with the arrival receipt. Each
sample contains x/y and a four-bit walkable-exit mask (north/east/south/west), read
from the exact hash-verified archived map. Junctions and dead ends are computed
from those samples. These are static access measurements, not resource discovery,
Pokémon sightings, battle outcomes, player observations or a rendered animation
claim. Cancelled or stalled journeys never produce a completed report. A survey
cannot be added or changed halfway through the same journey.

The durable public world journal displays the report title, measured point count,
junctions/dead ends and exact map revision. History lookup retains the full route
samples so a configured author can choose a later route or project based on real
terrain instead of treating an NPC's assertion as evidence. The reporting actor
can react; canonical actors such as Steven can independently consider reports on
their existing exact-revision `journey_interests`. Their goals are not changed
automatically, and this does not claim that they travelled with the scout. Existing
canonical story scripts, player parties, saves, and native capability negotiation
are unchanged.

This candidate currently supports the existing archived plain XL and opened cave
geometry admitted by region-character validation, not richer habitat simulation.
It relies on the existing bounded author service for deciding what to investigate
and how to act on the result. No new model service starts implicitly. Tests use
real authority commits and deterministic author fixtures; live-model choice and
full rendered integration remain Maya's QA gates.

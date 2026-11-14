# General persistent place creation

This draft extends #301 (space authoring), #300 (props) and #299 (capability
runtime). Native #32 remains pinned at 30a4fae1b19340225926d350895a30e516615a8c.
No shared world is replaced and no player or NPC is silently moved.

`world.create_place` is available in the general tool catalog for canonical and
world-owned characters. Arguments:

- `label`: literal ASCII menu label, 1..20 characters.
- `blueprint`: JSON string <=700 characters, within the normal step-size bound.
  Existing `cave_blueprint` keys: rooms as `[x,y,width,height]`, links as room-index
  pairs, entrance_room, exit_room. Optional style rooms/rounded/organic/maze,
  seed uint32, corridor_width 1..3. Room rectangles fit inside 1..29.

The existing deterministic compiler creates connected rooms/corridors and native
entrance/exit. SharedCave validates the complete plain format-1 map. The authority
archives the exact bytes, assigns the normal durable place identity and pins the
immutable revision in `world_region_revisions`. Archive, region-opened history,
identity and tool receipt are one transaction. A failed receipt leaves no place.
Exact duplicate geometry is refused; callers should reuse the existing place,
not invent a second identity or rename existing content. The action is bounded
at 32 opened regions; it never deletes old content to make space.

The receipt contains actual place_id, revision, label, side, walkable tile count
and required client capability REGION1. Geometry creation is the actual world
effect, not simulated construction, travel, discoveries, resources or a quest.
Characters choose parameters and subsequent actions rather than a named preset.

## Player path and native limitation

Compatible clients discover the destination through existing REGION LIST/menu,
select it while safely outside a generated area, transfer and ACK exact geometry,
and enter through the existing generated cave entry. Other players may select
other destinations independently. Reconnecting/restarting retains the opened
place. Existing admission, old-client refusal and original campaign rules remain.

**Native builds need GENERATED_WORLD_REGIONS=1 for this menu.** The current
Expansion makefile defaults that flag to 0. This draft intentionally does not
change release defaults: Maya must enable and playtest the existing feature when
integrating this capability. Authority publication is usable with the tested
REGION1 reference client now, but default native builds cannot discover/select
these new regions. This is not seamless cross-region travel, arbitrary Hoenn
editing, NPC cross-map movement, new tilesets or XL region admission.

## Validation

Tests compile different geometry for two actors and exercise real authenticated
REGION LIST -> SELECT -> transfer -> ACK -> valid entry -> restart/revisit.
They preserve the current shared map and original actors, reject duplicate and
invalid geometry/legacy selection, and inject receipt failure to check atomicity.
The socket is an in-memory transport into production authority; decisions are
fixture plans, not live model calls. Full linked native/rendered QA remains Maya's.

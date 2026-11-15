# Experimental own-Secret-Base sharing

This is a direct player-to-player game interaction using Emerald's actual saved
Secret Base records. It is not an agent-built room, an NPC relocation or wholesale
record mixing. No mail, TV records, unrelated friends' bases or save files are sent.

## Player path

Both players need the matching native candidate built with
`python scripts/build_expansion.py --development --experimental-secret-bases`.
The feature defaults off until linked/save QA. Stand adjacent in the same world
location, with chat enabled and no script, battle or other activity active.
The sender types `/base share NAME` in the native chat box. This explicitly offers
their own base location, decorations, trainer name/ID/gender and a recorded copy of
their current non-egg party (species, levels, moves, held items, personality and
average EVs, as in original record mixing). It does not transfer actual Pokémon.
The recipient gets a private explanation and `/base accept TOKEN` or
`/base decline TOKEN`. Offers expire after 60 seconds and are session-bound.

Both players must have received Secret Power and be outside Secret Bases. The
native importer validates the fixed version-specific semantic format before it
changes anything. The initial codec supports the current game language and basic
letter/digit/space trainer names; unsupported glyphs are refused, never rewritten.
An empty save slot is used, or the same recorded owner's base
is updated. Another owner's occupied location, the player's own location, a full
registry or malformed data is refused. Registered status, visit count and daily
battle status survive an update, so refreshing does not reset an existing battle.
No unrelated base is evicted. A successful native status says to save normally.
There is no automatic disk save and no server claim that import or saving happened.

After import, enter the actual base entrance in Hoenn after reloading the map.
Original Secret Base decoration rendering, registry and owner-battle scripts use
the new record. This does not grant Secret Power, reset story flags, place free
items in bags or change player Pokémon. Vanilla base battles reconstruct recorded
teams using existing mechanics, not the original Pokémon's full opaque state.

## Privacy, recovery and compatibility

Only the sender and explicit recipient receive offer messages. The fixed payload
is held briefly in authority memory; it does not enter persistent world history,
model context or public chat. The native `/base` prefix never falls back to chat;
older clients using that prefix on this host get a private unsupported notice.
An older server may reject/disconnect an unknown BASE protocol request, but cannot
broadcast it as CHAT. On timeout/disconnect there is no automatic retry or inferred
success. Acceptance consumes the offer once, and a late unmatched native response
cannot import it. Retry by issuing a new offer after checking local status.

## Tested and remaining

Component tests execute native C export/validation/import, send its actual bytes
through authenticated authority offer/accept dispatch, and import the delivered
bytes with the native implementation. Tests cover own/other bases, capacity,
daily battle state, expiry, session changes, range, replay and private routing.
They do not establish a linked game build, rendered base entry or disk save/reload.
Maya must verify those, native command entry and failure paths before enabling.

Based on app #351 / engine #47, not released RC12. Preserve the released pair
f484577b606348d07337387f14f75ab8cf4970b6 /
f7a813317d1b9fec803b48b682f5d74245c79037 during integration. No release is changed.

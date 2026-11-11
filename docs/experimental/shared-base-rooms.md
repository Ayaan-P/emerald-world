# Matching public Secret Base rooms (experimental draft)

This slice lets opted-in players meet inside the same published native Secret Base layout. It does not replace Emerald's base ownership, entrances, furniture placement, visitor registry or recorded-team battles.

## Player path

1. Create and decorate a base through stock Secret Power and owned-furniture mechanics.
2. Explicitly publish it using the existing `/neighborhood publish yes` flow. That existing publication shares the trainer name/ID, layout and recorded party; it is not made automatic here.
3. A visitor may browse `/guild bases`, download and explicitly install the snapshot, subject to the existing conflict/free-slot checks, then enter its original Hoenn entrance normally. Normal Save remains their own choice.
4. Inside the matching published layout, each participant chooses `/neighborhood meet on`. Matching nearby players become visible through the existing peer renderer. Existing adjacent trainer interaction can record an actual meeting against this room identity.
5. `/neighborhood status` reports waiting, matching or refusal. `/neighborhood meet off`, disconnect, leaving, stale state, publication withdrawal or a changed layout stops room admission. No forced teleport, vote or party mutation.

The opt-in sends only a digest of the installed owner identity/location/decorations/positions. It does not send a current party, inventory or story flags. Matching is client-reported content, not anti-cheat attestation. The matching publication must be unique; cloned owner/layout publications are refused rather than guessing which account's room is intended.

## Boundaries

- Native room feature defaults OFF (`EW_SHARED_BASE_ROOMS=0`). App opt-in: `--development --experimental-base-rooms`; publishing/importing additionally uses the existing `--experimental-secret-bases` switch.
- Requires this matching server and native pair. Old server behavior is not repaired by a client-only upgrade.
- Server deliberately isolates all Secret Base interiors by default, including legacy/unopted-in clients. Otherwise unrelated bases with the same ROM map could appear together. Ordinary Hoenn presence is unchanged.
- Room matching covers the saved published starting layout, not live shared furniture editing. Local balloons, mats, PC type, recorded owner NPC and stock base battles remain personal. No synchronized toy-state or shared battle outcomes are claimed.
- World-authored generic tile/object overlays are excluded from private base maps; there is no base-aware authored object mutation in this slice. Fly-to-friend does not expose these interiors as landing destinations.
- A changed layout requires a matching explicit re-publication and recipient update outside the base through existing import rules. The feature never imports or re-publishes automatically. Recorded-party-only publication changes do not split an otherwise identical room.
- Three-second authority leases, renewed by the native client in eligible field context; idle expiry schedules a fresh snapshot. Stale channel, stale sequence, wrong physical map, removed publication and ambiguous clones fail closed. Disconnect may have the ordinary short bounded expiry delay.
- No real save was used; no save layout/schema, inventory, battle reward, trainer flag or ownership mutation was added.

## Verification and integration

Based on app #494 `4e9cb1a6de9dd683b3682ca7c010541c7c2a9c98` and native #132 `8dea9e7f4ea77e22f3e1dd88da84b1b880ed7174`. Independent branches; Maya's branches are untouched. The general SHA helper is reused from published native #133, without its Cut feature.

Run `python test/test_base_rooms.py` in the app draft. Twelve synthetic checks exercise actual server snapshot/link admission/transport/adjacent-meeting methods, publication replacement/removal, clone ambiguity, channel freshness, expiry, normal-route compatibility, and actual native encoder/hash/protocol code with UBSan. Native changed C files were syntax-checked with recovered headers for flag 0 and 1; an existing deprecated-party alias warning remains in the unchanged exporter.

Full exact native build, rendered two-client base entry/exit, furniture/PC transitions, controller behavior during a native link activity, imported-save reload and extended idle/disconnect QA remain for integration. Component tests are not a playtest. Do not enable in a release based on this draft alone.

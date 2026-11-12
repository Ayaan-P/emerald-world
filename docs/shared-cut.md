# Shared ordinary Hoenn Cut paths (experimental)

Independent draft stacked on app #477 / native #115. Default `EW_SHARED_CUT=0`; build with `--experimental-shared-cut --development` only for matched disposable clients pending linked QA. This is not shared terrain, a regional story continuation or Rock Smash support.

## Actual player flow

Both friends first tag up normally. Each separately enables **Share Cut with tag** in the native peer menu. This is connection-local consent for their current tag, not saved settings or consent inferred from tagging. It permits reporting their completed nearby cuts and receiving matching temporary tree removals. Toggle off stops new reports/removals. Disconnect or a changed tag clears local consent; a new session requires opting in again.

On an ordinary outdoor Hoenn map, one player uses the original Cut interaction or party field move. The stock learned-move/badge checks, confirmation and animation remain native. Only after its actual `removeobject` does a new hook capture the completed tree identity. It waits for a ready field before sending a bounded report. A nearby, opted-in companion in the same map visit sees that actual tree disappear and can pass its former object collision. Their Cut script is never invoked; they receive no HM, badge, item, reward, Cut attribution or trainer/story credit.

The recipient checks the current map, visit, local ID, exact coordinates, original Cut script, cuttable-tree graphics and a temporary flag. This first slice is restricted to the existing **Hoenn towns-and-routes map group**, including the Route104 tree verified at (35,22), local native template and FLAG_TEMP_11. It excludes dungeon/interior trees, Kanto, generated objects, grass cutting, Strength and Rock Smash. Rock Smash's Rusturf progression and encounter tail are deliberately untouched.

## Lifetime and failure behavior

Reports are current-visit, near-range client reports, not server-attested moves or persistent world ownership. Both parties must have current opt-in registrations. The server uses authenticated LINK identity, current active tag and ready same-region presence. The native recipient separately checks exact local geometry identity and readiness. No backlog is sent to late arrivals or an unavailable recipient. A source ACK means the bounded report was processed, not that the partner rendered it.

A source may retry the same sequence for up to five seconds while presence catches up. Replays acknowledge without applying again. Only one completed Cut report is pending at a time; a missed event is not reconstructed. Registration is acknowledged before any capture is accepted. Leaving field callbacks conservatively ends the network visit, including menus/battles; a fresh registration is required on return even to the same map. Old packets cannot affect that new visit. Native map loading continues to own temporary-flag reset.

Turning sharing off or disconnecting does not resurrect a tree already removed in the current visit, which could trap someone behind it. The existing stock temporary flag remains until its normal map lifecycle clears it. No new save format, auto-save, durable transaction or cross-save write is introduced. All changes occur locally on each client's validated temporary obstacle, not through copied story flags.

## Verification and limits

- Four real relay tests cover bilateral consent, recipient visit binding, revocation/tag disconnect, no late replay, source readiness retry, map/range/identity bounds and sequence replay.
- Compiled complete native module with deterministic field/object/link doubles covers the real completion hook's already-removed flag requirement, deferred ready-field sending, ACKs, wrong coordinates/scripts/permanent flags, stale visits, busy recipient, actual removal, idempotence, revocation and tag changes.
- Default-off no-op compilation, source hook placement and UI/pump wiring checked. Build-option and existing pin checks included.
- Exact native Makefile source wildcards include the new module. Existing map-group and template fields were read from the pinned native source.

Not a full native link, rendered Cut animation/menu or two-client playtest. Actual script assembly, map-load callback timing, object collision removal, TLS/presence ordering and save/reload behavior still require disposable-save linked QA. Full private native checkout remains blocked by shell Git authentication; source access is available through the connector. No real saves or live providers were used. Maya's branches and held payloads remain untouched.

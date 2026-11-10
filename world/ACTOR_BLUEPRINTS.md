# Durable JSON blueprints for actual content executors

The actor runtime keeps its existing six-step plan and 1,024-character step limits. Several real executors accept larger content (for example, a campaign document up to 6,000 characters). A direct plan could not author most of that supported space. Blueprints let the author construct data through bounded edits, inspect a frozen snapshot, and pass its `document` result to the existing executor. This adds no arbitrary execution, permissions, native payload or validator exemption.

## Tools

- `world.edit_blueprint(id, revision, patch)` creates an empty-object draft at expected revision 0, or edits the exact current revision. Patch is JSON up to 700 characters: one to four literal `set` or `remove` operations with JSON-pointer paths. Parent containers must exist; `set /array/-` appends. Root replacement must remain an object. Each successful edit produces a durable revision, digest and public patch-history event.
- `world.inspect_blueprint(id)` returns the exact JSON document string, revision and digest. A dependent tool can use the standard `{result: step_id, key: document}` reference. That snapshot does not change if the draft is edited later.
- `world.close_blueprint(id, revision)` makes a finished draft read-only and frees an active slot. It does not remove its document or history and cannot change previously published content. IDs cannot be reused for a different draft. Completed/closed documents remain inspectable by their owner.

Only the owning actor can inspect or edit its draft through these tools. Drafts are public fictional authoring data, not private storage: patch events and successful tool receipts are in public world history. Do not store player-private data, secrets or personal information. Current discovery lists only active draft metadata, not private player state.

The workspace permits 16 active drafts per actor and 128 per world; closing frees a slot, so these are not lifetime creation ceilings. A document is limited to 8,192 encoded bytes, nesting depth 12, arrays/objects up to 256 entries, bounded printable strings and signed 64-bit integer/boolean/null values. No floating-point numbers, executable objects, files, imports, network endpoints or code execution. Downstream limits remain unchanged: a blueprint does not make an oversized campaign, unsupported region, invalid story or unauthorized world operation valid.

## Connected use

An author can assemble a larger campaign across several edits/plans. Once inspected, it passes the snapshot to `world.publish_battle_campaign`. Players then enter through the existing campaign UI and independently play the normal optional trainer battles. Other content tools may consume appropriate snapshots under their own validation. Editing a draft alone never publishes anything or changes player gameplay.

The component test assembles a 16-node campaign rejected by the direct per-step size check, in four bounded edits plus inspect and publish. It then starts the actual campaign, exchanges the existing authority-side CHARACTER_CHALLENGE/RESULT protocol and advances/finishes the reported branch. These are client-attested reports, not a simulated or verified victory. Test content is not an installed fixed campaign.

Revision conflicts and failed patches leave the old document intact. Patch/history updates roll back with a failed outer receipt. Database restart recovery and immutable snapshot reuse are tested. Closing a draft does not undo an already committed publication.

## Scope and handoff

Based on draft #381 `8776bfa25815ff5f618e57345f328d70e07a1125`, retaining native #55 `babbe0e3272120523d509cecf22705f158429586`. Not based on released RC12. Maya owns integration, rendered/live validation and release. Existing denied uploads and the separate unpublished provider-budget change are untouched. No live provider sessions were run. The old spectating stream remains app-disabled. This is an authoring capability with real existing gameplay consumption, not a new native UI or full linked-game playtest.

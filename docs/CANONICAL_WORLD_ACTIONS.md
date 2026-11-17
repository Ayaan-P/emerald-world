# Cast-owned actions in the shared story world

The existing opportunity engine can now contain explicitly actor-owned scenes.
These are **shared narrative simulation**, not physical NPC travel, new native
services, inventory transactions or canonical story flags. They change real
persisted place qualities and which `/story` choices explorers can see next.

A scene may declare `actors: ["canon_rydel", "canon_wally"]`. Such a scene is
world-once, has no private mystery prerequisite, and may read/change only place
qualities. Players cannot consume it. Existing scenes without `actors` retain
normal player behavior and cannot be taken over by cast actors. Other scenes can
respond to the resulting shared qualities, including making different choices
available to players or to another actor. No predefined cast arc ships here.

Current eligible actor actions are exposed as public `cast_world_actions` in
inspection (first 32). Each includes the exact pack, scene, place, revision,
actors, requirements-satisfied choices and effects. No player profiles or private
choices are loaded. A character author can choose one existing action using:

    world_action: {pack, scene, choice, place, revision}
    intentions: [{id, kind: "world_action", target: pack, reason}]

The place must be in the actor's established interests, and the normal canonical
revision/evidence validator still applies. The ordinary authority loop executes
one eligible retained action per five-second pass. The scene's allowlist, current
revision, eligibility and quality bounds are rechecked at commit. Stale/withdrawn
work produces no result. The public receipt, shared state and one-time intention
receipt commit together. Eight total completed retained actions per actor bound
this dispatcher. Restart does not replay actions. Manual `fulfill` cannot claim
execution. Busy/stale actors do not starve other eligible actors.

Other characters interested in that native place can independently react to the
actual receipt. They need not agree, join, or act. Public history/journal names
the responsible actor and the authored result. No automatic player choice,
reward, private relationship credit, actor location or completed native activity
is inferred. Existing story packs must explicitly opt individual scenes into
actor ownership; arbitrary public player opportunities cannot be appropriated.

Validation uses an authored test-only workshop: Rydel independently opens a
public discussion, Wally observes the committed result and chooses to contribute,
and both players receive the changed actual `/story` menu. The full authority
loop hook, normal staging, reaction queue, native-chat dispatch, persistence,
rollback and player-table isolation are exercised. Author output is deterministic
fixture data, not a live-model or rendered native run. No native pin change.

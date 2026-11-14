# Consented recurring visitor relationships

Independent app-only branch after #422 at
`f43978f65bcb7998a2003e39d84f25d85a1c9c6a`. Not Maya #410/#72 or RC12.
Native #79 remains unchanged. Uses the existing native dynamic trainer protocol;
no held bridge or worker modification, native save allocation or live provider.

## Player flow and consequence

Default speech stays anonymous and existing challenges stay available. Beside an
active generated NPC, `/guild npc remember-public ID` displays the exact scope and
provides a one-minute, actor-version-bound confirmation token. Confirm with the
shown command ending in `yes`. This is separate from consenting to any battle.

The NPC can now remember future direct public speech and exact optional dynamic
battle reports under a random per-player/per-NPC visitor handle. The existing
agent independently chooses whether and how to appraise that visitor through
`world.appraise_player`; there are no prescribed arcs, scores or automatic trust.

An appraisal cites an exact subsequent linked receipt and sets a short personal
native greeting plus `open`, `invite` or `decline` for this optional challenge.
The same NPC may welcome one remembered visitor while declining another.
Snapshots send that greeting only to its authenticated player; ordinary native
interaction and explicit battle choice remain. `invite` is an invitation, not a
battle launch. The actual NPC team still comes from the existing validated roster
and opponent-freezing path. An active condensed-campaign binding takes priority;
this system does not gate stock trainers, core story or campaign progression.

`/guild npc memory ID` shows the player's current public handle, subjective
appraisal and challenge policy. `/guild npc stop-remembering ID` works remotely,
stops future links and personalized offers, clears this feature's direct account linkage
and active appraisal (existing speech-delivery records are unchanged), and restores ordinary optional-challenge behavior. It does
not delete already published history. A new grant creates a different handle;
old evidence cannot be reused for it.

## Public, not secret memories

Consent explicitly discloses that linked fictional history and appraisals are
public to world players and agents. The login name is not added to these public
records. Pseudonyms are not a promise of anonymity: other people may infer who
was present or recognize the speech. Do not enter personal information. Existing
public world events are not rewritten or deleted on revocation.

No prior speech, private campaign report, group conversation, unseen move,
private party slot, save field or unrelated player's record is retroactively
linked. Only subsequent direct speech addressed to that NPC and reports for a
battle frozen under the same active consent are eligible evidence. A different
NPC cannot appraise this handle. Appraisals are explicitly subjective fictional
interpretations; citing a report does not verify its contents.

## Cached menus, freeze and recovery

- Current consent/policy is checked on every actual challenge request, after
  ordinary identity/location/version/format checks. A stale cached invitation
  cannot bypass a later decline. Native refusal uses the existing rejection
  path; no bespoke menu animation or policy-version packet is claimed.
- Once the ordinary native opponent is frozen, later policy changes or consent
  withdrawal do not cancel/rewrite it. Existing disconnect/recovery behavior is
  unchanged. This does not add durable recovery of in-flight native battles.
- A result is linked only while the exact original consent handle is still
  active. Revocation, or revocation followed by re-consent, cannot link that old
  battle to new memory. The result remains an authenticated client report, not
  independent proof of victory or growth.
- Queued appraisals revalidate current consent and their exact evidence at
  execution. Revoked or other-player evidence is rejected, with no new appraisal.
- Consent/appraisal/evidence rows survive normal server restart. No private game
  save is changed. Confirmation offers are session-local and cannot survive a
  reconnect. Max 32 active visitors per NPC and 16 remembered NPCs per player;
  stopping relationships frees active capacity without deleting public history.

## Verification

Component tests exercise confirmation/expiry, no retroactive linking, player
isolation, actual snapshot text, native challenge refusal/freezing/report ACK,
old-menu versus current policy, immutable in-flight opponents, revocation,
re-consent, restart persistence, anonymous defaults, existing campaign exemption,
queued-author reaction and actual capability execution. Responses/plans are
fixtures, not live model outputs. No rendered native/multiplayer playtest or
current native build is claimed. Current native dialog refresh and rejection
presentation remain integration QA tasks.

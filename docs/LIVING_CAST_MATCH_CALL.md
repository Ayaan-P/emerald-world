# Living cast through the original PokéNav

Wally and Steven's existing registered PokéNav contacts can now add their current
world-authored response after the ordinary Match Call message. No extra contact
is invented for Briney or Rydel, no registration flag is written, and original
message selection, story flag effects, call-location restrictions and trainer
rematch behavior execute first and remain unchanged.

This is an outgoing call through the actual PokéNav call screen, not a chat
command or unsolicited interruption. The optional second segment uses the same
native message window and text printer. It waits at most the existing three-
second request deadline; B cancels the supplemental wait. Offline, unavailable,
old-server, wrong-contact, stale and malformed responses leave the ordinary call
intact. No automatic retry or background model request is added.

Optional CORE CALL requests bind authenticated trainer and current synchronized
save lineage. Native selection and original registration flags govern access.
As elsewhere, client registration is attestation, not server-side anti-cheat
proof. The authority returns the current authored actor dialogue, or this
trainer's already selected conversation reply while its actor version remains
current. Other players' choices are not used. A character revision naturally
changes the next call; no predefined call script or arc is shipped.

A remote call is deliberately not an original-actor visit: it cannot authorize
Steven companion battles, accept physical-location proposals, acknowledge field
conversation memory, grant rewards or alter progression. There is no claimed
new relationship learning or simulated phone agreement. This adds a reusable
normal-game route to current cast responses without requiring another walk to
the original NPC. Existing configured author services still own world decisions.

Tests cover actual authenticated CALL wire output, different trainers, revision
fallback and restart; production native request/parser/timeout/cancel logic and
PokéNav loop functions compile with explicit engine/window doubles. The native
loop prints the original segment before the supplement and retains the old
rematch branch. Full linked PokéNav rendering, text pagination, B timing and
real-world network behavior still require Maya's QA. No native pin change.

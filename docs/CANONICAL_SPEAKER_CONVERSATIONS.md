# Speaker-led cast conversations with optional listeners

The existing cast `council` proposal now supports an explicit `mode: "speaker"`.
Its public question and two/three options use the same bounded authoring contract;
omitted mode remains the older optional unanimous policy. Neither mode is a
universal narrative-ownership rule, and the author ships no predetermined arc.

At the original NPC, `/guild cast ACTOR converse` opens a five-minute conversation
with that trainer as speaker, regardless of guild leadership. Other guild members
explicitly join with `listen ID`; up to four total participants can join. The
speaker and listeners can visit independently, rather than being forced into one
modal scene. Native original scripts and individual progress are unchanged.

Listeners use `advise ID OPTION`; the speaker uses `choose ID OPTION`. The speaker
may choose against every suggestion or with no listeners. Listeners may leave and
remove their pending advice; the speaker leaving cancels an unfinished session.
An actor version change, expiry or guild membership removal/change invalidates
an open session. Nobody else can choose for the speaker, including the leader.

`conversation ID` lets opted-in participants review the public question, suggestion
counts, chosen answer and any later public authored character response. This works
through the current in-game guild-chat interface. It is not synchronized native
dialogue animation or automatic retransmission of each original text box.

The choice creates one durable `canonical_speaker_decided` world receipt with
anonymous advice counts. It explicitly means speaker choice, not unanimity or
participant agreement. The character's author can independently consider it and
choose a supported response/action. No story flag, reward, relationship score or
activity completion is implied. Repeating a command cannot republish completion.

Only public authored question/options/dialogue enter this shared conversation.
Private native reflections, save IDs, party data and personal choices are never
mirrored to listeners or the world author. Individual relationship/encounter
records remain unchanged: listening is not fabricated personal conversation
memory. Session participant/advice identities stay in host-accessible authority
storage; the public receipt contains no trainer or guild names. The opt-in view
explains the public choice/advice-count scope before a listener can advise.

Tests exercise a nonleader speaker rejecting the leader's suggestion, explicit
listener opt-in, personal-choice isolation, actual author reaction and later shared
public response, restart, withdrawal, expiration, version change and capacity.
These use deterministic author fixtures and actual authority dispatch. No native
patch/pin change is needed; Maya still owns rendered/live-model integration QA.

## Paired native field overlay

The paired native candidate adds SELECT at the existing reviewed original-NPC
supplemental conversation point. It renders the public question using the actual
field message box, then explicit start/join disclosure, optional advice counts
and paged choices. SELECT changes pages, A starts/joins/advises/chooses, and B
returns to the original script. No new NPC, script pointer, flag write or field
unlock is introduced. B returns from the overlay, not withdrawal of previously
shared advice; the existing leave command remains available.

The new optional DIALOG request is bound to the actual preceding CAST actor,
map alias, save lineage, actor version and two-minute context lifetime. A fresh
field position is still required. This is a narrow native-script context exception
to chat's ready=1 rule, because original NPC scripts hold controls. Chat cannot
use that exception, and the implementation never sets the player's readiness.
Native preview is read-only; joining and choosing require explicit separate A
input. Late/stale/refused/expired responses cannot switch actor or retry a choice.
Older authorities refuse the optional request and the original script resumes.

The field overlay shows each participant's own role and public option/advice
counts. It is not a synchronized camera/cutscene, automatic listening to someone
else's private text, or real-time polling of every suggestion. Reopening the
panel refreshes the state. An asynchronous later author response appears through
the normal next original-NPC conversation; the guild-chat transcript also remains
available. Actual rendered timing, input feel and complete linked native build
still require Maya's QA. Tests compile the real adapter with deterministic field
message/input stubs and exercise authority admission at script-locked readiness.

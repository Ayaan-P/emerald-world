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

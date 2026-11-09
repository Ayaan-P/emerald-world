# Destination encounters

A journey can now seek another existing world character and carry a bounded
public fictional message. The normal character_actions response adds:
meet {target, expected_version, text}. It requires journey, an active target
on the exact same generated revision, and an endpoint adjacent to that target.
The visitor's endpoint dialogue must equal the message (one literal line,
maximum 28 characters), so the native object displays the same authored words.

The authority rechecks both real validated object positions, target version,
presence, walking state and pending battle at arrival. If the target moved,
changed, became unavailable, or is busy, the result is a missed encounter.
The visitor can reconsider that real outcome; the recipient receives no
message-driven author turn for a miss. There is no automatic retry or chase.

A valid adjacent arrival records public_message_delivered. This is a message
delivered through the actual shared-world authority, not an assertion that a
native chat animation or every client's rendering finished. The target's dialogue,
goals and relationships are unchanged by delivery itself. A followed target may
independently respond or choose another supported action through its existing
configured author runtime. Its resulting dialogue is the actual native object's
text, not a separate scratch simulation.

The one-time encounter is atomic with the journey receipt and final position.
Restart does not redeliver it. Original canonical NPCs remain untouched; their
exact-revision journey interests can observe these public encounters without
implying they attended. No player errands, player messages, private conversations,
automatic affection, fabricated battles or canonical relocation are involved.

Tests run a 19-step authority journey to a second actual world object, verify
adjacency/message delivery, recipient-specific reaction admission, independently
authored changed native-object dialogue, one receipt and restart. Additional
tests cover changed targets producing a miss without delivery, invalid targets,
wrong endpoint and mismatched visible message. Author output is deterministic
fixture data; live model and rendered conversation are not verified.

This is app-only use of the existing movement/object bridge. No native payload
or engine pin changes; Maya owns integration, rendered QA and release.

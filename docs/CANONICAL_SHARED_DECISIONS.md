# Shared conversations with the existing cast

An agent can attach an optional `council` to Wally, Briney, Steven or Rydel:
`{question: literal public text, options: {short_id: literal label, ...}}`.
Two or three options are supported. This is a question about the character's
possible priorities, not an executable story branch or a player chore.

Original-NPC supplemental dialogue points players to the existing guild chat.
`/guild cast ACTOR council` shows the terms and current player's answer.
`/guild cast ACTOR decide VERSION CHOICE` records that authenticated player's
answer. `withdraw` removes it before agreement. Each player must have visited
and be ready at the original actor's safe conversation location, but they can
answer separately while the others explore. No simultaneous modal scene or
teleport is introduced. The existing native hooks are sufficient.

The whole current guild must have two to four members. No leader/host can answer
for anyone else. Only all members explicitly choosing the same option commits
one public `canonical_council_agreed` receipt. Disagreement, abstention and
withdrawal produce no public preference. The record contains the question,
choice, actor version and group size, never names, guild identity or individual
answers. Private answers remain in host-accessible authority storage and are
not sent to the author. Membership edits invalidate pending answers, including
leave/rejoin between commands; completed history is not erased. A new actor
version requires new answers. The same version cannot publish twice for a guild.

The actor's existing author loop can independently consider the true result and
change goals, dialogue or another supported action. It is not compelled to obey,
and no predetermined story arc is shipped. Tests use a deterministic reaction
that changes the original Rydel response after a real two-player agreement and
separately exercise four players. No personal relationship, achievement, reward,
party state, native progression flag or canonical movement is inferred.

Pending choices and completed receipts survive restart. Tests cover private
pending votes, disagreement without leader override, reconsideration, withdrawal,
membership churn, version/location admission, restart, four-player unanimity and
actual subsequent CAST output. Native pin unchanged. These are authority tests,
not a rendered group-conversation or live-model quality claim; Maya integrates
and performs full QA.

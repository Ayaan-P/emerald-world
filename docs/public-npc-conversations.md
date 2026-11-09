# Open-ended public speech with recurring world NPCs

Players can use existing in-game chat:

- `/guild npc` explains the public scope.
- `/guild npc nearby` lists ready nearby recurring NPC identities.
- `/guild npc say-public ID MESSAGE` delivers up to 80 printable characters of explicitly public fictional speech.

The player must be authenticated, ready and within two tiles of the active character on the exact same map/revision. Movement, missing/retired NPCs, stale player state and pending battles refuse speech. The existing reserved `/guild` namespace does not fall back to room chat on unsupported servers. No actual guild membership is needed for this NPC interaction.

Speech becomes an anonymous public world-history event: no trainer name, team or save data is supplied to the author. The text is player dialogue, not trusted instructions, proof of an event, or permission to break world rules. Do not put personal information in public speech. It does not enter private original-cast relationship memory; #293 remains a separate private conversation feature.

An enrolled/configured character agent gets an independent result-driven author turn, subject to existing provider settings and budgets. It can ignore the message, answer through `world.reply_player`, or compose any already permitted plan. No model is started by the command and no answer is guaranteed. The public reply is retained in world history. Native chat delivery happens only after the authority transaction commits, and only if the same initiating connection is still nearby; delayed replies are never redirected into another session. Existing history remains the fallback if the player leaves.

This covers world-owned recurring NPCs, including those on ordinary native maps. It does not duplicate original Wally/Steven scripts or override canonical services. Tests use authored responses and actual command/event/runtime paths, not a live model or rendered game. The native pin is unchanged, and the experimental capture feature stays disabled. Maya owns integration and QA.

# Open-ended public speech with recurring world NPCs

Players can use existing in-game chat:

- `/guild npc` explains the public scope.
- `/guild npc nearby` lists ready nearby recurring NPC identities.
- `/guild npc say-public ID MESSAGE` delivers up to 80 printable characters of explicitly public fictional speech.

The player must be authenticated, ready and within two tiles of the active character on the exact same map/revision. Movement, missing/retired NPCs, stale player state and pending battles refuse speech. The existing reserved `/guild` namespace does not fall back to room chat on unsupported servers. No actual guild membership is needed for this NPC interaction.

Speech becomes an anonymous public world-history event: no trainer name, team or save data is supplied to the author. The text is player dialogue, not trusted instructions, proof of an event, or permission to break world rules. Do not put personal information in public speech. It does not enter private original-cast relationship memory; #293 remains a separate private conversation feature.

An enrolled/configured character agent gets an independent result-driven author turn, subject to existing provider settings and budgets. It can ignore the message, answer through `world.reply_player`, or compose any already permitted plan. No model is started by the command and no answer is guaranteed. The public reply is retained in world history. Native chat delivery happens only after the authority transaction commits, and only if the same initiating connection is still nearby; delayed replies are never redirected into another session. Existing history remains the fallback if the player leaves.

This covers world-owned recurring NPCs, including those on ordinary native maps. It does not duplicate original Wally/Steven scripts or override canonical services. Tests use authored responses and actual command/event/runtime paths, not a live model or rendered game. The native pin is unchanged, and the experimental capture feature stays disabled. Maya owns integration and QA.

## Native interaction entry point

Paired native draft #37 at b9c54b6851965f11a0b785503234b8ff3efa9aa0 adds START **Talk publicly** to the recurring NPC's post-greeting interaction menu. It opens a bound NPC composer with a PUBLIC-world-speech notice. Type the message itself, Enter to send, Escape to cancel. No slash command is required. Battle, expedition and leave remain available. Platforms without the native chat editor retain their original menu.

The composer uses the same reserved command gate and the app's proximity checks. Unsupported servers can refuse the command; it is never sent as ordinary room chat. Slash-like text inside the composer is literal NPC speech, not a second command. A delayed agent response is still subject to the session/location rules above.

The paired test compiles actual native menu/editor functions with platform fixtures and sends their emitted command through the authenticated app CHAT handler, then checks the reply snapshot. This is not a linked or rendered game playtest. Maya should verify actual key bindings, field-to-editor focus, cancellation, typing readiness, coexistence with battle/expedition, and two-client interaction before release.

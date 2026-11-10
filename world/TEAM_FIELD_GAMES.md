# Authored team field games

`world.publish_flag_arena` makes an immutable capture-the-flag arena available on the existing activity board. Canonical and generated authors choose a normal map, two bases, time and capture limits. An optional four-point `starts` array enables 2-v-2; without it the original duel is unchanged. Starts alternate Red, Blue, Red, Blue, must be distinct, and each must be at most one cardinal tile from its team base. Bounds validation is not walkability validation: authors/operators must playtest routes.

Players use `/guild play list`, `/guild play start flag ID`, and `/guild play share flag`. Guildmates use `/guild play join HOST`; join order determines alternating teams. Each runner sees their assigned start and uses `/guild flag ready`. All four must join and stand ready before a team match begins. Ordinary movement remains independently controlled. The current native private-command client suffices; no new protocol or upload is needed.

Each team has exactly one flag. Either teammate may steal it, but it cannot be duplicated. Opposing nearby runners tag carriers; teammates cannot. A tagged runner must return home after the existing cooldown. A team can score only while its own flag is home. Existing busy-field, freshness, disconnect, timeout and cancellation behavior remains. Flags and scores are logical authority gameplay communicated through existing chat/status, not newly rendered flag sprites or native battles. No bags, saves, rewards, Pokémon or story flags change.

Completed scores are private to the participating trainers using the existing results table. Four participants retain their alternating team assignment and score across restart. In-progress matches cancel on authority restart, as before; no fabricated resumed match or completed result. Authors see published arena definitions, not private matches, participants or results. NPCs create opportunities, not commands compelling players to join.

Publication in an actor plan uses the same outer transaction as its real receipt. Immutable identity and the existing 64-arena capacity remain. No live model call is required for local tests. This is not an unlimited arena archive or anti-cheat proof: positions are authenticated client attestations.

## Verification and ancestry

This branch is based on draft #379, app `b02e737c3188915cb97722c49cbd74835a6fdef8`, and retains native #55 `babbe0e3272120523d509cecf22705f158429586`. It is not based on released RC12. Maya retains integration, rendered playtesting and release ownership. The uncorrected spectating stream remains rejected by the app. Denied native/privacy/documentation uploads and the unpublished vision-budget correction are untouched; do not run live provider sessions.

Component tests drive actual CHAT and STATE through the authority: four-player board joining, countdown, teammate immunity, opposing tags, unique carrier, capture, private persisted scores, disconnect cancellation, author plan execution, bounds and transaction rollback. Existing duels remain covered. No rendered four-client playtest or live model behavior is claimed.

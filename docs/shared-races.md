# Simultaneous multiplayer field races

This is a reusable 2–4-player race system using actual ordinary walking or native
Pokemon mounts. Unlike the baton relay, every racer follows the same checkpoint
sequence at once, completing individual laps and retaining individual split times.
It does not replace Pokemon battles or implement Fire Emblem tactical combat.

## Create and play

A configured character author discovers `world.publish_race(course=JSON)`. The
course defines id, title, 2–4 distinct nearby start pads, 2–16 ordered checkpoints,
1–8 laps, a 60–1800 second limit and a mounted boolean. Positions are
[map_group,map_number,x,y]. Course IDs are immutable; publish a new ID for a revised
course. Registration does not start a race or fabricate any result. Public course
catalogs are available in agent discovery and the existing activity board.

Players in a guild use `/guild play list`, then `/guild play start race COURSE`.
The host may `/guild play share race`; guildmates see `/guild play open` and join
with `/guild play join HOST`. Direct `/guild race start COURSE` and
`/guild race join CODE` also work. Each player stands on the assigned pad and
uses `/guild race ready`. Mounted courses require an actual supported party mount
via the existing `/mount 1..6`. No mount, Pokemon or item is granted by this system.

After a three-second countdown everybody runs. `/guild race status` reports that
player's current lap and next checkpoint. Current chat displays checkpoint and
finish updates. `/guild race records` shows only the requesting trainer's retained
times. `/guild race leave` ends the session. Joining/starting relay, flag or mystery
activities while racing is rejected, and vice versa.

## Actual result and recovery semantics

Checkpoints require fresh native presence or validated contiguous native mount
trail samples, never interpolation across a warp, diagonal or missing report.
Each racer's ordered cursor is independent. Timer continues through menus/battles;
only ready field presence advances checkpoints. Dismount, mount change, lost
movement reports, disconnect, guild change, timeout or stale presence ends the
session without inventing a finish. Already committed individual finishes remain.
Live races intentionally do not resume after server restart; completed times do.

Positions remain client attestations under the existing world's trust model.
These are recreational records, not anti-cheat results. There are no rewards,
guild XP, player-save writes, scripted campaign outcomes or publicly published
results. Participating racers see each other's finishes; unrelated guild members
do not receive private race messages. Records are trainer-account recreational
history, not transferable campaign progress across saves.

Native map bounds and start-grid shape are validated. The app map catalog does
not prove normal-map walkability or course fairness: authored routes need rendered
playtesting. Generated map aliases are rejected rather than mixing revisions. No
new native rendering, obstacles, race HUD, automatic warp or canonical NPC motion
is claimed. Existing chat is the race interface; all movement is ordinary gameplay.

## Pair and integration

App-only independent branch atop #339, using unchanged native #40
8e409094ccd226a66c9cf8bfef2f545f2be52c28. No dependency on doubles, evolution,
rendezvous or television drafts. It is not based on released RC12 app
f484577b606348d07337387f14f75ab8cf4970b6/native
f7a813317d1b9fec803b48b682f5d74245c79037. Maya owns preserving release fixes,
integration and rendered multiplayer QA; this work does not alter her release.

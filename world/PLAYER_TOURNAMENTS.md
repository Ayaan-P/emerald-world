# Session-bound player tournaments

Separate child of native #62, paired with an app child of #400. Not RC12-based.
Frozen #384/#56 and previously denied/uncertain operations remain untouched.

An agent publishes a generic 2/4/8-player singles bracket. Players inspect
`/guild tournament show ID`, then `/guild tournament join ID yes` explicitly
publishes their trainer name and match results to ALL world players/agents.
The bracket starts at capacity using enrollment order. Each entrant retains an
independent save lineage and their own party. No level normalization, clause
engine, rental parties, prizes, save writes or forced PvP are added.

`/guild tournament fight ID` uses the existing native invitation path. Both
players must be nearby and eligible in ordinary Hoenn; the opponent accepts in
the normal activity UI. Generated-area restrictions are not bypassed. A separate
U WATCH message binds reporting only to that admitted singles session. Normal
native win/loss/draw terminal handlers send outcomes, excluding recorded battles
and other modes. Reports retry at most ten times and reset on disconnect.

The server requires observed native handshake, both authenticated enrolled save
lineages, and complementary win/loss reports before advancing. These remain
client reports, not authority simulation or anti-cheat proof. One report or
session closure never awards a win. Draw/disagreement/interruption requires
both entrants to use `/guild tournament retry ID yes` after the native session
ends. Unsupported termination paths, including unsupported forfeits, do not
invent results. Server restart interrupts in-flight attempts; exact prior
reports remain durable, but late missing reports cannot complete recovered
attempts. A new jointly authorized attempt uses a new session identity.

`/guild tournament leave ID` removes a waiting entrant or cancels a started
bracket without inventing a winner; it does not terminate an existing native
battle. No organizer can pick a winner. Completed brackets remain queryable.

Tests: actual native reporter compiled with fake transport, terminal hook source
checks; actual Python consent/handshake coordinator and durable bracket tests,
including disagreement, disconnect, restart, save switches, duplicate reports,
withdrawal and four-player progression. No linked/rendered/two-client battle
playtest, turn execution or live provider call. Native outcome perspective and
full game interruption behavior still require integration QA.

Organizers can use world.cancel_tournament on their own unfinished bracket to
release active capacity, without forcing any native battle to stop.

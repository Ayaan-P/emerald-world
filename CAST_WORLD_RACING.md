# Agent-authored simultaneous field racing in the living-world candidate

This combines #362 with the existing #344 racing system rather than implementing
another relay or fixed character scenario. No native changes are required:
#52 d209d94393086ceda8a5f63de5c3cfe4732ac432 already carries the ordinary
walking/mount presence and private-command client needed by this feature.

## Connected experience

Either original or generated actors can choose world.publish_race, defining an
immutable 2–4-player course from ordinary-map checkpoints, laps and mount rules.
The existing cooperation capability also lets one character ask another to design
a course; the recipient can decline or independently publish and return its real
publication receipt. Neither publication nor correspondence starts a player race.

Players discover it with /guild play list, explicitly start it with
/guild play start race COURSE, optionally share the lobby with guildmates using
/guild play share race, and join through /guild play join HOST. Each player stands
on the assigned pad and uses /guild race ready. After the countdown all racers
move at once, following their own ordered checkpoints, not a relay baton.
Mounted courses use existing /mount party mounts. /guild race status shows the
next target; /guild race records shows the requesting trainer's own finish times.
The interface is existing private chat, not a new native race HUD.

No race results are sent to character authors or public world history. Native
movement reports are recreational client attestations, not anti-cheat proof.
No XP, rewards, forced warps, player save changes or character growth occurs.
Record scope is trainer-account recreation, not cross-save campaign completion.
NPCs author courses; they do not themselves race or simulate a finish.

## Ancestry

App parents: #362 d497605e6f0d6bed9439d1d5b0e64284c636b754 and
#344 a02e9d5fd3d70d75d39ede6f1b919a73fd0fde2f.
Native remains #52, not #344's older #40 pin. Conflicts resolved in capability
registration/discovery and cumulative regression lists; current campaign,
contest, outbreak, television, companion and cooperation capabilities retained.
Existing activity conflicts remain guarded in both directions.

Not based on released RC12 app f484577b606348d07337387f14f75ab8cf4970b6 /
engine f7a813317d1b9fec803b48b682f5d74245c79037. Neither release nor Maya's
integration branch was changed. Maya owns reconciliation and final QA.

## Verification boundary

Connected regression uses actual authority plans for Rydel's request, a generated
researcher's independent acceptance/publication and typed receipt, then actual
authenticated player CHAT/STATE to start/join/ready/run/finish that course. It
checks personal records remain out of agent context/history and guild XP stays
unchanged. Existing race regressions cover four simultaneous racers, mounted
trails, disconnect, restart and activity conflicts.

Authors in tests are deterministic fixtures, not live models. Normal-map bounds
are validated, not native walkability or fairness. Routes still need rendered
playtesting. No linked multiplayer, visual racing or live-provider QA is claimed.

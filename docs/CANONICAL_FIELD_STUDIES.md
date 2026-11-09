# Character-owned field studies

This slice adds a reusable actual project to the existing cast, not a simulated
NPC journey. Wally, Briney, Steven or Rydel can retain a study intention, choose
survey locations from inspected archived geometry, and install an optional
exploration activity through the existing bounded author initiative.

## Author contract

A canonical action may contain study with exact revision, literal title, and
2..8 sites {id, x, y}. The archived template must be plain XL v16, and every site
must be walkable, away from native endpoints, with a distinct arrival radius.
The study intention kind is study; target is the full archived revision.
Fulfilling it requires a new actual study installation receipt.

The authority installs the survey and records ownership in the same transaction
as the character change and intention receipt. Existing surveys cannot be
overwritten or claimed; one immutable study per revision, at most eight per
actor. A rejected site rolls back the whole character action. This does not
activate a map, alter geometry, spawn an actor, change story flags or player
saves, grant rewards, or enroll players.

The existing followed-character queue can attempt the retained task without a
new player event. It still requires host-configured author enrollment and uses
existing bounded attempts. No background model service is enabled by this PR.
The reaction adapter supplies only allowlisted exact public archived geometry,
checked against the inspected world boundary; it excludes private survey visits.

## Visible play and feedback

At the original actor, /guild cast steven studies (or the other actor's key)
lists installed studies and whether the exact map is active. Inside the matching
acknowledged generated outdoor map, /explore start joins the ordinary private
landmark survey. The existing survey tracks actual authenticated client presence,
provides nearby site guidance, and retains arrivals across restart.

These are proposed observation sites, not proof of rare rocks, hidden items,
wildlife, or anything the character supposedly discovered. No new sprites or map
markers are added; the existing exploration guidance is the visible interface.
The player can decline, stop, or keep all progress private. Replacing the active
map suspends matching visits; it does not migrate the study to a different map.

Existing explicit /explore share LANDMARK confirm publishes only that arrival,
not a trainer name or unshared trail. An installed study's actor and immutable
project digest are attached to the public event, allowing that actor to
reconsider a goal through the normal author queue. Private visits and even
private survey completion do not trigger author work. Client-reported arrival
is not anti-cheat proof or an independently simulated expedition.

## Validation and limitations

The integration regression uses the production character compiler, authority,
archive, initiative queue, survey protocol, public sharing, and durable database.
It demonstrates retained intention -> actual survey installation -> optional
private arrival -> explicit public share -> changed character goal -> restart.
Author outputs are deterministic test fixtures, not a live model run.
Additional tests reject non-walkable sites, absent archives, duplicate arrival
neighborhoods, and takeover of existing surveys with transaction rollback.

This is app-only reuse of the current plain XL survey protocol. No native
payload, app native pin, original map scripts or canonical battle are changed.
It intentionally does not support other template formats until their actual
survey implementation is supported. Full rendered play remains Maya's QA gate.

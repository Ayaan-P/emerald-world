# Optional shared research publication

App draft based on #398 (5a42b90b), paired native draft based on #60.
Not RC12-based; Maya's frozen #384/#56 remain untouched.

In ordinary field play, `/research` explains the audience. `/research publish yes`
reads the current personal seen/caught flags once and publishes that snapshot to
all connected world players and configured agents. Includes existing history,
not just future sightings. No party, trainer name, location or individual Pokemon
is in this payload. The server keeps a permanent combined aggregate. Stop does
not retract previously accepted findings; disconnect cancels pending retries.
Use `/research status` for the receipt, `/guild research` to browse/search.

Two flags per hexadecimal digit keep the full current National Dex below the
existing 1024-byte server line limit. Up to 1026 entries are supported; larger
engine catalogs fail closed. No save flags or rewards are changed. Client reports
are not authoritative captures or proof of present ownership. This is a ledger,
not a replacement for anyone's personal Pokedex or completion rewards.

Tests compile the actual one-shot sender against fake transport/read functions,
check opt-in, snapshot retries, ACK, reset and finite timeout. The native read
adapter and transport/chat hooks have source checks only. Full linked build,
rendered UI and two-client testing remain for integration QA. No live providers.

## Exploring the shared research gaps

`/guild research unreported [page]` lists known catalogue entries with no public
report; `/guild research uncaught [page]` also includes entries reported seen
but not caught. Pages are zero-based and show eight entries. These compare only
the voluntary shared aggregate to the server's existing species catalogue. The
catalogue may omit species; absence does not imply a species is obtainable,
that no trainer owns it, or anything about a player's private Pokédex. Browsing
never modifies a save or publishes a report.

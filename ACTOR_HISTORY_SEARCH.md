# Source-preserving long-term character history

Recurring characters no longer have to rely only on the latest prompt or the eight best matches in automatic recall. Both canonical and generated actors can choose `world.search_history` and `world.read_history` through the existing configured author and plan runtime. These are public-record research tools, not new senses or an automatic personality rewrite.

## Connected workflow

An agent can search past correspondence involving another character, find older shared campaign reports, or browse changes to a stable place. Search returns up to eight original records ordered oldest first, with a fixed `through` boundary and a `cursor`. The next plan step can reuse those scalar results to continue paging. `first_sequence` allows a search followed immediately by an exact source read without manually supplying a known event ID. It is zero when no match exists, not an invented source.

A search query is a JSON object with optional `actor`, `event`, `place`, and `terms`. Actor matches the public character, sender or recipient fields, not private trainer identity. All supplied filters combine. Literal terms search the existing changed-content index; they do not search all prose. An empty query pages the retained public log. Reuse the returned boundary for consistent paging even if new events arrive. The coverage-start sequence explicitly marks the limit of retained history.

Large records are not silently truncated into summaries. Search identifies their exact sequence and fields. Read accepts that sequence and an empty root path or a JSON pointer such as `/after/goals`. Large containers return their fields or array length for narrower reads. Oversized scalar values are explicitly unavailable within the output bound. Original provenance, claims and limits remain part of the source.

Results enter the existing durable capability receipts, author inspection and normal result-driven replanning. The agent may then choose a supported action or revise its own plan. The tools do not grant new permissions, award experience, treat client-reported battles as verified victories, or force a particular response. No live model behavior has been demonstrated by these component tests.

## Privacy and history integrity

Only `world_memory` records are readable. Private events, saves, private conversations and player records are not queried. A public historical assertion is not proof that the assertion happened, and a public source is not first-hand observation by the reader. Current world inspection takes precedence over stale historical state. Record text remains data, never operator instructions.

Search and read receipts remain durable plan outcomes, but are excluded from subsequent history searches and cannot themselves be recursively read. They are not indexed as place changes, so looking up a location does not replace its actual first/latest changes in automatic recall. The original append-only records are not rewritten, summarized away or deleted.

## Ancestry and verification

App-only child of #369 at 04e27ab7e87d4bfe2aae933100a74e30731e27b7. Native pin remains #55 babbe0e3272120523d509cecf22705f158429586. Neither pending native upload is included or retried. The inherited app spectating mitigation still refuses the uncorrected stream; spectating is not made usable by this change.

This feature stack is not based on released RC12 (app f484577b606348d07337387f14f75ab8cf4970b6, native f7a813317d1b9fec803b48b682f5d74245c79037). Maya's release and integration remain untouched.

Tests cover records beyond the old recall window, fixed-boundary pagination with intervening appends and restart, private-record exclusion, exact nested reads, source provenance, literal filter validation, retrieval non-recursion, place-index integrity, and actual canonical plan search-to-read composition with durable replanning receipts. Native gameplay, linked multiplayer and live provider QA remain unverified.

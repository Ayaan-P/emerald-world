# Provider author to capability loop

This draft extends #305; it does not add another action primitive or change
provider recipients, credentials, runtime enrollment or release defaults.

## Verified wiring and repaired gap

The launcher-configured RuntimeGM already sends inspected `actor_runtime`
capability schemas, affordances and receipts to the selected author. Both official
Claude Messages and OpenAI Responses adapters accept the same typed character
changes, including `changes.plan`. Provider tool calling is deliberately disabled:
the model authors a bounded plan, then the authority executes registered tools.
Committed succeeded/blocked tool results enter public history and the existing
followed-character queue schedules another independent decision.

Previously RuntimeGM recovered prior source only from its own authored jobs.
Navigation/population/object capabilities stage new source independently. After
one of those actions, the live hash no longer matched the worker's cache, and a
subsequent typed replan lacked the actual mechanic to preserve.

The new host-admin `mechanic_source(expected_hash)` returns only the exact current
admitted source after checking live candidate, durable module and SHA256. It takes
no filesystem path, is not a public player-wire command and does not put source
in general inspection. RuntimeGM uses it only when its verified local cache misses;
stale/mismatched replies fail closed rather than rewriting from an obsolete base.
The author prompt now explicitly describes general capability composition,
receipt references, pending plans, replanning and the provider/authority boundary.

## Honest validation

The new end-to-end fixture runs the real configured worker, GM prompt/compiler,
provider decoding, admin dispatcher and required sandbox. API responses and local
socket transport are fake; no credentials, live network calls or API spend.
It authors create-place -> populate, checks the real result, and asks the author
to replan from the changed source. On this executor the required sandbox cannot
create a NETLINK_ROUTE socket, so both provider cases explicitly skip at deployment
rather than bypass isolation or claim full-loop success. They remain runnable in
an environment where the existing sandbox works.

Separate passing tests retrieve an actual admitted population-capability source
through the worker with an empty author cache and reject stale hashes or altered
source. Existing authority, compiler, provider-contract and capability tests remain
in the aggregate suite. Live provider quality, full loop under a functioning
sandbox and rendered integration still need Maya's QA.

Followed actors are still explicitly enrolled through existing setup. This patch
does not silently subscribe every newly spawned character, expand private data
sharing or create a separate model process per fictional record.

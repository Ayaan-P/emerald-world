# Explicit interchangeable author backends

The living-world runtime now selects an author backend independently of its
queue, prompt, canonical action compiler, sandboxed candidate tests and atomic
world admission. This is not an arbitrary executable/endpoint plugin loader.
Only reviewed transports can be registered in `world/author_backends.py`.

## Public character/world author

Three explicit choices exist. There is no fallback or automatic model change:

- `codex`: the existing reviewed tool-disabled CLI, unchanged version isolation.
- `openai-responses`: official `https://api.openai.com/v1/responses`.
- `anthropic-messages`: official `https://api.anthropic.com/v1/messages`, API
  version `2026-10-21` as documented in the current official reference.

For direct API operation, the host supplies its authorized credential through
its own process environment (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`). Do not put
keys in repository files, command arguments, chats, queue records or documentation.
This implementation creates no keys, reads no credential files, and installs no
SDK. It uses Python's standard HTTPS library with certificate validation, fixed
destinations, no proxy environment inheritance and no redirects.

Select an actual model ID available to the host's account. No API model is
assumed equivalent to the legacy `openai-codex/...` alias. Availability, model
quality, pricing and authentication are not verified by local preflight.

    python3 -m world.runtime_gm check-author \
      --provider anthropic-messages --model ACTUAL_CLAUDE_MODEL_ID
    python3 -m world.runtime_gm run --state-dir AUTHOR_STATE --socket TRANSPORT_SOCKET \
      --provider anthropic-messages --model ACTUAL_CLAUDE_MODEL_ID

Replace the provider/model explicitly for OpenAI. Existing enrollment, retained
intentions and author actions stay unchanged. `--once` remains useful for a
bounded first integration run. Starting `run` authorizes real provider requests
from that host process; this document is not evidence that any were made here.

## Isolation and failure semantics

Direct requests supply no model tools and explicitly select no tool use. No
agent containers, files, plugins, shell, filesystem or computer tools are
registered. Only the bounded prompt is sent. OpenAI requests also set
`store:false`; this is not a promise about every provider's retention policy.
Anthropic storage/retention follows the host's provider account terms.

A bounded JSON result is the only accepted output. Tool-call output, refusals,
truncation, incomplete replies and unexpected schemas fail closed. Provider
errors and credentials are not logged. One attempt is made; uncertain timeouts,
HTTP failures and rejected output never trigger a retry or another provider.
The outer existing author subprocess deadline and byte limits remain in force.

Returned world source/actions still pass the existing independent candidate
sandbox, tests and authority validation. Selecting another model grants no new
world operation or access to player saves. The backend itself does not execute
model tool calls. The public author receives the same configured public-author
context as before, not private character reflections.

## Private responses retain their recipient boundary

Existing private grants explicitly name OpenAI. Therefore the private worker
supports only legacy `codex` or direct `openai-responses`. Anthropic processing
of those grants is rejected before claiming them, even when invoked through
Python rather than the CLI. A future private provider change requires a
provider-bound consent design, not reuse of an existing grant.

    python3 -m world.private_cast_worker --socket TRANSPORT_SOCKET \
      --provider openai-responses --model ACTUAL_OPENAI_MODEL_ID \
      --watch --max-jobs 8

No private grant, key or provider configuration was changed during development.

## Evidence and official interfaces

Contract tests use fake transport responses, including both providers' output
into the actual canonical compiler/authority, no-tools payloads, refused output,
redirect/proxy suppression, byte limits, one-attempt errors and private-recipient
separation. They do not demonstrate live authentication, account model access,
provider quality or rendered gameplay. No live API request was made.

Official documentation inspected:
- https://developers.openai.com/api/docs/guides/text
- https://developers.openai.com/api/reference/resources/responses/methods/create
- https://platform.claude.com/docs/en/api/messages/create
- https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons

To add another provider, add a fixed official endpoint, explicit credential
source, bounded tool-free request codec and strict result decoder with tests.
Do not expose an arbitrary URL or reuse private OpenAI grants for another
recipient. Keep backend-specific preflight and no-fallback behavior explicit.

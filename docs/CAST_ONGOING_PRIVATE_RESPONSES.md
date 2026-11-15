# Ongoing private cast responses

This candidate connects actual shared-conversation choices to a remembered,
individual next response from the original character. It does not simulate
unobserved experiences, change a story battle, or make the shared author aware
of private relationships.

## Player journey

After meeting the supported original character and enabling their existing
private memory, use `/guild cast rydel reflect follow`. The preview identifies
the OpenAI provider, data, save scope and future processing. Confirm its code
once. The grant covers this character on this save, not other trainers or saves.
An initial response can be prepared. Subsequent responses require a new actual
shared-conversation choice or advice by this trainer. Merely reading a response
or listening silently never triggers a new request.

For example, Alice advises travelling together while Bob chooses independent
journeys as the speaker. The private worker sees each trainer's own recorded
role and choice plus the speaker's actual decision. Each can receive a different
next Rydel response through the existing original-NPC interface. The resulting
interpretation is tentative, not a permanent assertion of personality. It is
retained only after the native client acknowledges displaying that exact reply.

`/guild cast rydel reflect stop` withdraws this save's ongoing grant and cancels
its automatic work. `remember off` or `forget` also cancels grants for that
trainer and actor. Existing memory controls and ordinary dialogue remain usable.
Manual one-time reflection remains available.

## Explicit host operation

The existing private cast worker must be explicitly started with `--watch`.
It processes at most `--max-jobs` (default 8, maximum 32), then exits; it also
exits after `--idle-seconds` without work (default 300, maximum 3600).
Provider failures stop the worker and are not automatically retried. Nothing
starts a background model on server boot or as a side effect of viewing an NPC.
The host still supplies the configured provider/model and credentials.

Each grant admits at most four requests per UTC day. Reconfirming an active
grant preserves its usage. This is a gameplay bound, not a financial spending
cap; deliberately stopping and creating a new grant resets that grant's budget.
At most sixteen save grants per trainer/actor are retained. Existing one-time
requests migrate without loss to save-specific queues, so two saves do not
replace one another's pending replies.

## Evidence and limitations

Tests exercise the actual authority, shared dialogue decisions, private worker
claim/finish, original-NPC response selection, acknowledgement, persistence,
revocation and two-save migration. They use deterministic model callbacks, not
a live provider. Shared inspection/history remain unchanged by private work.
No new native wire or hook is required. Linked native rendering, live-model
quality/cost and the complete integrated player journey remain Maya's QA.

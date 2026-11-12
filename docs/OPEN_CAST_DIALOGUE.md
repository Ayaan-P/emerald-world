# Open-ended private dialogue with the original cast

Separate app follow-on to #286, paired with native #28 fde183bffe37c0ef8963f15f050782418cbafcb5. Builder PIN, gitlink and manifest match. Neither consolidated branch is changed.

## Player experience

Meet the original Wally, Briney, Steven or Rydel at an existing supported safe conversation. With that actor's existing private memory enabled, use `/history ask ACTOR your question` to send up to 96 plain ASCII characters to the host-configured OpenAI private character responder. `/history ask` explains the destination and syntax. There is no new standing grant: each command is one explicit question.

The responder may answer in character using that save's remembered conversation, the actor's current goal and prior tentative perspective. It cannot execute tools, edit world state, promise an accomplished action or access other players. The question's context is frozen when asked; merely talking again while waiting does not cancel it. A changed character version, revoked memory or forgotten save prevents its use.

Talk to the same original actor to see the eventual answer. Only acknowledgment of that exact displayed answer retains its tentative perspective for the next question. This enables a continuing personal conversation instead of choosing only fixed authored options. Normal scripts and services remain unchanged. These answers do not mutate shared goals or award trust, affection, Pokemon growth or rewards.

## Runtime and privacy

Requires the existing explicitly enabled private worker (`world.private_cast_worker`) and its reviewed OpenAI configuration. This branch does not start a model automatically, add arbitrary providers or broaden existing conversation grants. If no worker is running, the question remains pending; the native message says so. The existing reflection status command reports pending/running/ready. No live model call was made during development.

The command is intercepted in native `/history` handling and sent only over negotiated CORE, never ordinary chat or a public fallback. Authority requires a fresh original-actor context, current native save, private memory opt-in and no pending/unseen answer. A repeated question does not replace an in-flight one.

`/guild cast ACTOR reflect cancel` cancels that save's private question. Remember-off or forget revokes pending work; forget also removes existing actor memory. Question text is erased after the exact reply is displayed or cancelled; only the bounded tentative perspective remains. Host operators can access local storage. Existing private model grants name OpenAI; this feature does not silently switch them to another provider.

## Evidence

Paired regression compiles the actual native adapter, emits a question packet and routes it through actual authenticated authority and the isolated responder claim/result path. Tests verify literal input cannot return world code, persistence/restart, save mismatch, withdrawal, no public history/module changes and perspective retention only after display. Native disconnect never sends a fallback chat message.

Component tests are not a linked-game, rendered UI or live-model quality claim. Maya owns integration, full build, co-op/save QA and release.

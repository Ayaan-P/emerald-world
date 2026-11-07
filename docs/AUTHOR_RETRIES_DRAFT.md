# Opt-in model candidate retries

The model author accepts `--attempts 1..3`, defaulting to one. When explicitly configured for more attempts, it can request a fresh candidate after a completed, tool-free model response fails local schema or geometry validation. It sends only generic validation guidance, not the rejected model text, and shares the original total deadline across attempts. Unexpected tool activity, malformed provider events, provider failures and timeouts fail immediately without retrying. Nothing is written or replaced until a candidate passes validation. Additional model calls may incur charges.

Tests mock the provider; no real model call is made. Native CI attempts to reject one mocked candidate, accept the next and play the resulting offline painted story in game. Until CI passes that game path is unverified. Visual quality, real model reliability and multiplayer are not established. This draft stacks #224 and its predecessors; integration is separate.

# Shared XL wilds draft

This extends the offline 127×127 agent-authored wilds format to the authenticated world authority. A capability-negotiated `CAVE10` client receives the same SHA-256-bound map, validates the rows and stages the native world. Older clients are denied entry to XL areas, while capable trainers retain separate saves and may occupy the same area. The owner publishes the existing inert binary with the same owner-only controls used for prior generated maps. Only closed, connected geometry with fixed entry and exit is accepted.

This is a first shared geometry slice. XL maps do not yet have agent event graphs, generated NPCs, or mutable shared terrain. It does not invoke a language model. Save isolation and individual progression rely on existing generated-world behavior. Area replacement is subject to existing authority occupancy rules.

Tests cover native C wire identity and rejection of corrupted or truncated transfers, native staging and map layout, and two simulated authenticated authority connections with independent admissions and positions beyond the old boundary. These are not real socket, two-client visual or full runtime tests. Native CI should be checked on the exact draft head; integration with the current RC requires reconciliation of the predecessor stack.

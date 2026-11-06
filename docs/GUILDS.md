# Player guilds

Guilds are optional persistent groups in one World authority. Players use the existing in-game chat (T, or Ctrl+T if T is bound) without installing a new game-side protocol. The server must run the version with guild support. This feature doesn't change Pokémon saves, parties, inventory, battle mechanics or the game engine and is intended to carry over when the Expansion client supports the existing chat protocol.

- `/guild create NAME` creates a guild and makes you its leader.
- `/guild invite TRAINER` invites an existing trainer in this world. Online invitees see a private message; offline invitees can check `/guild invites`.
- `/guild accept NAME` or `/guild decline NAME` responds to an invitation.
- `/guild info` and `/guild roster` show your own guild. `/guild leave` leaves it.
- `/guild kick TRAINER`, `/guild transfer TRAINER` and `/guild disband` are leader actions. A leader must transfer leadership or disband rather than leave.
- `/g MESSAGE` sends chat only to currently connected guild members. Guild chat is session-only; offline players do not receive missed chat.
- `/guild help` shows the commands in the game chat. Names use 1–24 letters, digits, underscores or hyphens. A guild can have up to 50 members, and each trainer can be in only one guild per world.

Invitations and membership persist in the world authority's SQLite database; they are not trainer saves. Guild commands are authenticated as the logged-in trainer. There is no automatic battle pairing, shared inventory, bank, shop or missions yet. Player-visible results and invite notices use private chat snapshots; unrelated trainers do not receive them. The server does not provide a delivery guarantee after a connection failure, so check `/guild info` or `/guild invites` before repeating an uncertain command.

Tests use disposable in-memory or temporary databases and in-memory chat handling. They do not establish live two-client or Expansion-client compatibility. No host deployment is included.

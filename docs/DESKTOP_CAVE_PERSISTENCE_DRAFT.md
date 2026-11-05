# Durable generated caves for local hosts (draft)

A local desktop-hosted world now enables the existing generated-cave persistence mechanism when it starts. Once a host explicitly generates or publishes a cave, the authority stores the validated full template in that world's own SQLite database and reloads it on the next host start. The content hash and geometry/biome/wildlife remain the same across restarts. Replacement remains owner-controlled and refuses to replace an occupied cave. New worlds without a cave still start normally.

This changes local desktop-hosted worlds only. The separate server CLI retains its existing explicit `--persist-generated-cave` option and default; remote and hosted-service operators are unaffected. This does not change or merge trainer saves. A corrupt persisted cave causes startup validation to fail rather than silently loading a different layout.

A local, socket-free test creates an authority through the desktop host path, generates and stores a v5 cave with a mocked provider, restarts the authority, verifies the same cave identity and checks a separate trainer save remains unchanged. It does not simulate a real two-client session, desktop GUI interaction or live model call. Parent draft integration and safe admission/return limitations remain.

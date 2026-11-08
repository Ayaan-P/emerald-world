# Preserve native saves when copying

Expansion's ordinary native save contains a 28-byte header plus 131,072 bytes of
flash. The former 128 KiB backup/import limit rejected these valid files. The
experimental regional extension also needs its envelope and both snapshots
preserved. Its maximum file size is 147,524 bytes.

This change only copies opaque bytes; it does not convert saves or declare them
compatible. The selected native engine still validates header, version, CRC and
ABI, and will refuse unsupported extended files. Vanilla retains its 128 KiB
limit. Engine-specific limits now cover backup, base64 import, HTTP request
bodies and the existing file picker. The latter reads the bridge's advertised
limit, rather than assuming every engine saves a raw flash image.

Ownership, single-link/no-symlink checks, nonblocking profile locks, private
permissions, atomic non-overwriting backup publication and no import-back remain
unchanged. Offline copy already preserves files up to 1 MiB without truncation.

Verification uses synthetic v1, current regional v2 and maximum-sized v2 files.
Both snapshots survive backup and offline restore byte-for-byte. Oversized
files, active profiles, links and existing backup targets are rejected. Browser
tests cover a maximum file, pre-read rejection and size growth during reading.
No human saves, sockets, running game or network service are used.

This fix does not add native Kanto gameplay or publish the separate engine draft.

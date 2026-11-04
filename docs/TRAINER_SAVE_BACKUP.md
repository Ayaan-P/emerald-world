# Back up a local trainer save

Each trainer's game save lives on their own device. A host account backup does **not** include Pokémon progress. This command makes a separate private copy of one online or offline trainer save without contacting the server.

1. Save normally in the game, then close the game. The tool uses the existing profile lock and refuses to copy while a cooperating launcher or game holds that lock.
2. Choose an existing destination directory that you own and that other users cannot write to. Choose a new filename; existing files are never replaced.
3. Supply the exact local world directory and trainer profile key:

```sh
python3 -m world.save_backup \
  --world /path/to/local/world \
  --trainer YourTrainer \
  --destination /path/to/private-backups/emerald-backup.sav
```

For a separate offline adventure, add `--offline`. The tool creates a mode-0600 file containing the exact bytes of the chosen save. It writes a temporary file first and publishes the complete copy without overwriting an existing destination. The destination filesystem must support hard links and directory synchronization. Keep a second copy on encrypted storage you control.

The tool checks file type, ownership, size and concurrent changes; it does **not** validate whether the game's save contents are healthy. The lock protects against cooperating Emerald World processes, not arbitrary programs that ignore it. If disk synchronization fails after publication, a completed destination may exist; inspect it before retrying with a different filename.

This command only creates a backup. It does not overwrite an online profile or merge offline progress into it. The launcher can import a separate copy into a new solo adventure; automatic restoration into an online profile is not provided by this tool. Server-side worlds and owner credentials must be backed up separately.

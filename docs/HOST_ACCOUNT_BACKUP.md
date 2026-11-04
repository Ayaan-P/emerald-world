# Back up a hosted-world owner account

An owner profile is the private credential for managing that owner's hosted worlds. The original HOST ACCESS invitation alone cannot replace a lost profile after enrollment. Keep at least one protected copy of your owner profile somewhere you control, such as encrypted storage.

**Anyone with this file can manage your hosted worlds.** Do not post it, commit it, attach it to a bug report, or share it as a friend invitation. This backup contains no player saves or server-world data. Back those up separately.

## Make a backup

Choose an existing directory you own that is not writable by other users. Both the source profile and the resulting file must remain private. Replace the paths below with your actual locations:

```sh
python3 -m world.hosted_profile_backup backup \
  --source /path/to/private/host-profile.json \
  --destination /path/to/private-backup/host-profile.json
```

The command validates the profile locally, creates a new file with mode 0600, and never contacts the hosting service. It refuses to overwrite an existing destination. If the directory is on removable storage, ensure the filesystem supports Unix ownership and permissions, or use an encrypted archive that preserves them.

## Restore on another device

Copy the backup through a secure channel into a directory you own, make sure the file is mode 0600, and choose a **new** profile path:

```sh
python3 -m world.hosted_profile_backup restore \
  --source /path/to/private-backup/host-profile.json \
  --destination /path/to/private/host-profile.json
```

Restore validates the file's structure, not whether the hosting service is reachable or the credential is still accepted. It never replaces an existing profile. Keep the original until you have verified that the restored profile can access your hosted worlds. A saved host profile is different from a host-access invitation and from a world-join invitation.

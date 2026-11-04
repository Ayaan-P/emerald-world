# Trainer-save backups in the launcher

Once the separate trainer-save backup module from PR #139 is installed, open **Save backups** in the launcher. Save normally and close the relevant game, choose an online or offline profile, and select **Create backup** followed by **Download save**.

The original save is not changed. A profile lock prevents copying a game running through a cooperating launcher. The browser's downloads folder may not be private; move the backup to encrypted storage. The launcher does not validate whether the saved progress is healthy, and the backup contains neither host-account credentials nor server-world data.

The feature does not restore or merge a backup into online progress. A player can import a copy into a separate solo adventure using the existing solo flow. For direct file-based backup outside the launcher, see [trainer save backup](TRAINER_SAVE_BACKUP.md).

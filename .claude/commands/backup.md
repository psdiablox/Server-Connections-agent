Check backup status or trigger a manual backup of all Docker volumes.

**Usage:** `/backup [check|run]`

- `check` (default or explicit): show backup status without running
- `run`: trigger a full backup now

Connect via `ssh -i ~/.ssh/server_key deploy@82.223.64.68`.

## For `check`:

1. **List available backups**:
   ```bash
   ls -lhtr /opt/backups/ 2>/dev/null && du -sh /opt/backups/$(ls -t /opt/backups/ | head -1)
   ```

2. **Latest backup age** — flag if >24 hours old.

3. **Named volumes vs backed-up volumes**:
   ```bash
   # What exists
   docker volume ls --format '{{.Name}}' | grep -v '^[a-f0-9]\{64\}'

   # What was backed up in latest backup
   ls /opt/backups/$(ls -t /opt/backups/ | head -1)/
   ```
   Flag any volume that has no corresponding `.tar.gz` in the latest backup.

4. **Disk space check** — enough space for another backup?
   ```bash
   df -h /opt
   ```

## For `run`:

1. Confirm disk space is sufficient.
2. Run:
   ```bash
   sudo bash /opt/server/scripts/backup.sh
   ```
3. After completion, verify all named volumes have a `.tar.gz`.
4. Show total size and confirm 7-day retention was applied.

## Important reminder

Backups on the same server as the services are **not disaster recovery** — they protect against accidental deletion but not against server loss. The backup files at `/opt/backups/` should be copied off-server regularly (S3, external drive, another machine).

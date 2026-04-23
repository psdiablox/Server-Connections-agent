Check backup status or trigger a manual backup.

**Usage:** `/backup [check|run]`

- If `$ARGUMENTS` is `run` or empty: trigger a backup.
- If `$ARGUMENTS` is `check`: only show backup status without running.

## For `check`:

1. List available backups: `ls -lhtr /opt/backups/ 2>/dev/null | tail -20`
2. Show size of latest backup: `du -sh /opt/backups/$(ls -t /opt/backups/ | head -1) 2>/dev/null`
3. Check latest backup age — flag if >24 hours old.
4. List named Docker volumes: `docker volume ls --format '{{.Name}}' | grep -v '^[a-f0-9]\{64\}$'`
5. Cross-check that each named volume has a corresponding `.tar.gz` in the latest backup.
6. Report which volumes have backups and which are missing.

## For `run`:

1. Show what will be backed up (named volumes + infrastructure configs).
2. Run `bash scripts/backup.sh` and stream output.
3. After completion, show backup size and location.
4. Verify each named volume produced a `.tar.gz` file.
5. Report total backup size and confirm retention policy applied.

Always remind the user: **backups on the same server as services are not disaster recovery** — the backup files should be copied to an off-site location (S3, external drive, another server).

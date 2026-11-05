# Backups

Three scripts in `deploy/scripts/`. **Nothing here is switched on yet**: no cron job, no systemd unit and no offsite destination exist. They sit in the repo until the owner approves enabling them.

| Script | What it does |
|---|---|
| `backup_db.sh` | Daily `pg_dump` of the production database, gzip, verification, rotation (7 daily + 4 weekly) |
| `backup_offsite.sh` | Copies the verified backups off the server over SSH (`rsync`). Does nothing until `OFFSITE_TARGET` is set |
| `restore_test.sh` | Restores a backup into a throw-away **local** PostgreSQL and checks it |

The older `deploy/scripts/backup.sh` (7-day retention, Telegram upload, no verification) is left untouched. `backup_db.sh` replaces it once enabled; do not run both.

## What counts as a good backup

`backup_db.sh` writes to a `.partial` file and only keeps the result when all of this holds:

1. `pg_dump` and `gzip` both succeeded (`pipefail`);
2. `gzip -t` passes;
3. the size is at least `BACKUP_MIN_BYTES` (20 000) and not under half of the previous daily backup;
4. the dump contains at least `BACKUP_MIN_TABLES` (50) `CREATE TABLE` statements (production has 117).

If any check fails the new file is deleted, **older backups are not rotated away**, the script exits non-zero and, when `TELEGRAM_BOT_TOKEN` + `ADMIN_TELEGRAM_ID` (or `BACKUP_ALERT_TELEGRAM_TOKEN/CHAT`) are in `.env.prod`, the admin gets a Telegram message. A good backup gets a `.sha256` next to it; rotation (`KEEP_DAILY=7`, `KEEP_WEEKLY=4`) runs only after a verified backup. A Sunday's backup is also copied to `weekly/` (`WEEKLY_DAY=7`, ISO weekday).

```
/opt/backups/lms/
  daily/   lms_YYYYmmdd_HHMMSS.sql.gz (+ .sha256)   newest 7
  weekly/  lms_YYYYmmdd_HHMMSS.sql.gz (+ .sha256)   newest 4
```

## Run it by hand (read-only for the application)

```bash
cd /opt/lms && ./deploy/scripts/backup_db.sh            # default /opt/backups/lms
```

It runs `pg_dump` inside the existing `db` container (`docker compose ... exec -T db pg_dump`), so it never touches the application containers, the `bestway` project, volumes or networks.

## Restore test (do this regularly, on your own machine)

```bash
# copy a backup down, then, with a local PostgreSQL running:
PGHOST=127.0.0.1 PGUSER=postgres ./deploy/scripts/restore_test.sh path/to/lms_20261105_030001.sql.gz
```

The script refuses any host that is not localhost, creates `lms_restore_test`, loads the dump with `ON_ERROR_STOP`, checks the table count (≥ 50), that `django_migrations` has rows and prints the user count, then drops the database (`KEEP_DB=1` keeps it). Last result on this branch: PostgreSQL 17.11 restored a dump of a freshly migrated database, **117 tables, 162 migrations, 3 users, RESTORE OK**; a corrupted gzip is rejected, a too-small dump is rejected without deleting older backups, and `PGHOST` other than localhost is refused. A production dump has not been restored yet (needs a copy of a real backup).

## Offsite copy

The destination is not chosen. When it is:

```bash
OFFSITE_TARGET=backup@storage.example.com:/srv/grandec-backups \
OFFSITE_SSH_KEY=/home/deploy/.ssh/backup_ed25519 \
./deploy/scripts/backup_offsite.sh
```

It copies `daily/` and `weekly/` (`.sql.gz` and `.sha256` only, never `.env`), then runs `sha256sum -c` on the remote side and fails if it does not match. The remote must be encrypted storage under your control: a backup contains personal data. **`backup_offsite.sh` has not been run against a real host.**

## Turning it on (after approval)

Not done. When approved, one line in the `deploy` user's crontab, for example:

```
15 3 * * * cd /opt/lms && ./deploy/scripts/backup_db.sh >> /var/log/lms-backup.log 2>&1 && OFFSITE_TARGET=... ./deploy/scripts/backup_offsite.sh >> /var/log/lms-backup.log 2>&1
```

Before relying on it: confirm free disk space in `/opt/backups` (a dump is ~160 KB gzipped today), and run the restore test on a real backup once.

#!/bin/sh
# Nightly pg_dump into /backups (mounted from ./backups on the host), keeping BACKUP_KEEP_DAYS days.
# Restore: gunzip -c backups/voxfin-<stamp>.sql.gz | docker compose exec -T db psql -U voxfin voxfin
set -eu

while true; do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  file="/backups/voxfin-${stamp}.sql.gz"
  if pg_dump --no-owner --clean --if-exists | gzip > "${file}.tmp"; then
    mv "${file}.tmp" "${file}"
    echo "backup: wrote ${file}"
  else
    rm -f "${file}.tmp"
    echo "backup: FAILED at ${stamp}" >&2
  fi
  find /backups -name 'voxfin-*.sql.gz' -mtime +"${BACKUP_KEEP_DAYS}" -delete
  sleep 86400
done

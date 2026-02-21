$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $repoRoot "backups"
if (!(Test-Path $backupDir)) {
  New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sqlFile = Join-Path $backupDir "ridax_$stamp.sql"
$dumpFile = Join-Path $backupDir "ridax_$stamp.dump"
$countFile = Join-Path $backupDir "ridax_$stamp`_counts.csv"

Write-Host "Creating plain SQL backup: $sqlFile"
docker exec ridax-db pg_dump -U ridax -d ridax -F p > $sqlFile

Write-Host "Creating custom backup: $dumpFile"
docker exec ridax-db sh -lc "pg_dump -U ridax -d ridax -F c -f /tmp/ridax_$stamp.dump"
docker cp "ridax-db:/tmp/ridax_$stamp.dump" $dumpFile
docker exec ridax-db rm -f "/tmp/ridax_$stamp.dump"

Write-Host "Capturing validation counts: $countFile"
docker exec ridax-db psql -U ridax -d ridax -At -F"," -c "SELECT 'users', count(*) FROM users UNION ALL SELECT 'products', count(*) FROM products UNION ALL SELECT 'sales', count(*) FROM sales UNION ALL SELECT 'purchases', count(*) FROM purchases UNION ALL SELECT 'inventory_movements', count(*) FROM inventory_movements;" > $countFile

Write-Host "Backup completed successfully."
Write-Host "SQL:   $sqlFile"
Write-Host "DUMP:  $dumpFile"
Write-Host "COUNT: $countFile"

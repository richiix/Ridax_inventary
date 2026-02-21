param(
  [Parameter(Mandatory = $true)]
  [string]$NeonDatabaseUrl,

  [Parameter(Mandatory = $true)]
  [string]$BackupSqlPath
)

$ErrorActionPreference = "Stop"

$psqlUrl = $NeonDatabaseUrl -replace '^postgresql\+psycopg2://', 'postgresql://'

if (!(Test-Path $BackupSqlPath)) {
  throw "Backup file not found: $BackupSqlPath"
}

$resolvedBackup = (Resolve-Path $BackupSqlPath).Path
$backupFolder = Split-Path -Parent $resolvedBackup
$backupName = Split-Path -Leaf $resolvedBackup

Write-Host "Restoring backup into Neon..."
docker run --rm -v "${backupFolder}:/backups" -e "PSQL_URL=$psqlUrl" -e "BACKUP_NAME=$backupName" postgres:16-alpine sh -lc 'psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f "/backups/$BACKUP_NAME"'

Write-Host "Restore completed. Running validation query..."
$query = "SELECT 'users' AS table, count(*) AS rows FROM users UNION ALL SELECT 'products', count(*) FROM products UNION ALL SELECT 'sales', count(*) FROM sales UNION ALL SELECT 'purchases', count(*) FROM purchases UNION ALL SELECT 'inventory_movements', count(*) FROM inventory_movements;"
$query | docker run --rm -i -e "PSQL_URL=$psqlUrl" postgres:16-alpine sh -lc 'psql "$PSQL_URL"'

Write-Host "Neon restore + basic validation completed."

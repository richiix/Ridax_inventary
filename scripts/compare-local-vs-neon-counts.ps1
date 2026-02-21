param(
  [Parameter(Mandatory = $true)]
  [string]$NeonDatabaseUrl
)

$ErrorActionPreference = "Stop"

$query = "SELECT 'users' AS table_name, count(*) AS rows FROM users UNION ALL SELECT 'products', count(*) FROM products UNION ALL SELECT 'sales', count(*) FROM sales UNION ALL SELECT 'purchases', count(*) FROM purchases UNION ALL SELECT 'inventory_movements', count(*) FROM inventory_movements ORDER BY table_name;"
$psqlUrl = $NeonDatabaseUrl -replace '^postgresql\+psycopg2://', 'postgresql://'

$local = docker exec ridax-db psql -U ridax -d ridax -At -F"," -c $query
$neon = $query | docker run --rm -i -e "PSQL_URL=$psqlUrl" postgres:16-alpine sh -lc 'psql "$PSQL_URL" -At -F","'

$localMap = @{}
foreach ($line in $local) {
  $parts = $line.Split(',')
  if ($parts.Length -eq 2) { $localMap[$parts[0]] = [int]$parts[1] }
}

$neonMap = @{}
foreach ($line in $neon) {
  $parts = $line.Split(',')
  if ($parts.Length -eq 2) { $neonMap[$parts[0]] = [int]$parts[1] }
}

$tables = ($localMap.Keys + $neonMap.Keys | Sort-Object -Unique)
$ok = $true
foreach ($table in $tables) {
  $localCount = if ($localMap.ContainsKey($table)) { $localMap[$table] } else { -1 }
  $neonCount = if ($neonMap.ContainsKey($table)) { $neonMap[$table] } else { -1 }
  $match = $localCount -eq $neonCount
  if (-not $match) { $ok = $false }
  Write-Host ("{0,-20} local={1,-6} neon={2,-6} match={3}" -f $table, $localCount, $neonCount, $match)
}

if (-not $ok) {
  throw "Count comparison failed. Do not cut over yet."
}

Write-Host "Count comparison successful."

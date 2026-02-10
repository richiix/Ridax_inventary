param(
  [string]$EnvFile = ".env.cloudflare"
)

if (!(Test-Path $EnvFile)) {
  throw "No existe $EnvFile. Crea uno basado en .env.cloudflare.example"
}

docker compose -f docker-compose.cloudflare.yml --env-file $EnvFile up --build -d

Write-Host "Despliegue iniciado. Verifica estado con:" -ForegroundColor Green
Write-Host "docker compose -f docker-compose.cloudflare.yml --env-file $EnvFile ps"

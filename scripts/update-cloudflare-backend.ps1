param(
  [string]$EnvFile = ".env.cloudflare"
)

if (!(Test-Path $EnvFile)) {
  throw "No existe $EnvFile. Crea uno basado en .env.cloudflare.example"
}

docker compose -f docker-compose.cloudflare.yml --env-file $EnvFile up --build -d backend cloudflared

Write-Host "Backend actualizado y publicado por Cloudflare Tunnel." -ForegroundColor Green

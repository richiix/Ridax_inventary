# RIDAX Platform MVP

Plataforma web de gestion con backend Python y frontend moderno para RIDAX.

## Incluye en este MVP

- Panel principal con: Dashboard, Articulos, Inventario, Ventas, Compras, Informes y Configuracion.
- Backend `FastAPI` con `PostgreSQL` y control de accesos por rol (`Admin`, `Gerente`, `Vendedor`).
- Frontend `Next.js` responsive para escritorio y movil.
- Integraciones bidireccionales base para WhatsApp y Telegram (webhooks + envio).
- Soporte inicial para multi-divisa (USD base, tasas configuradas) y arquitectura lista para multi-idioma.
- API versionada (`/api/v1`) preparada para app movil (React Native) y catalogo e-commerce.

## Credenciales demo

- `admin@ridax.local` / `Admin123!`
- `gerente@ridax.local` / `Gerente123!`
- `vendedor@ridax.local` / `Vendedor123!`

## Ejecutar en local con Docker

1. Requisitos:
   - Docker Desktop
   - Docker Compose

2. Desde la raiz del proyecto:

```bash
docker compose up --build
```

3. Servicios:
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000`
   - Swagger: `http://localhost:8000/docs`

4. Prueba rapida de API (PowerShell):

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/auth/login" -ContentType "application/json" -Body '{"email":"admin@ridax.local","password":"Admin123!"}'
$token = $login.access_token
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/dashboard/summary" -Headers @{ Authorization = "Bearer $token" }
```

## Ejecutar en local sin Docker (opcional)

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg2://ridax:ridax@localhost:5432/ridax
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Variables de entorno

- Backend base: `backend/.env.example`
- Frontend base: `frontend/.env.example`

Para activar WhatsApp/Telegram real, completa estas variables en el servicio backend:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_DEFAULT_CHAT_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`

Variables recomendadas para recuperacion de contrasena por Telegram:

- `FRONTEND_URL` (ej. `https://app.tudominio.com`)
- `PASSWORD_RESET_TTL_MINUTES` (default `15`)

## Telegram en produccion (Cloudflare)

1. Asegura que el backend tenga URL publica HTTPS.
2. Configura webhook de Telegram hacia:
   - `https://TU_DOMINIO/api/v1/integrations/telegram/webhook`
3. Verifica el webhook:
   - `getWebhookInfo` sin errores.

Script helper incluido (`telegram-webhook.ps1`):

```powershell
# Ver estado actual
./telegram-webhook.ps1 -Action get -Token "TU_TOKEN"

# Configurar webhook
./telegram-webhook.ps1 -Action set -Token "TU_TOKEN" -PublicBaseUrl "https://TU_DOMINIO"

# Eliminar webhook
./telegram-webhook.ps1 -Action delete -Token "TU_TOKEN"
```

Comando util en bot:

- Enviar `/start` para recibir `chat_id` y vincularlo en Configuracion > General > Preferencias por usuario (Admin).

## Despliegue en internet (gratis y seguro, enfoque recomendado)

- Frontend en Cloudflare Pages.
- Backend FastAPI en VM propia con Cloudflare Tunnel (sin puertos publicos abiertos).
- Base de datos PostgreSQL gestionada o autogestionada con backup diario.

Flujo sugerido:

1. Desplegar frontend en Cloudflare Pages.
2. Levantar backend en VM con Docker.
3. Publicar backend por Cloudflare Tunnel a un subdominio privado.
4. Restringir origenes CORS y habilitar WAF de Cloudflare.

## Despliegue gratis en Cloudflare (paso a paso)

### 1) Frontend en Cloudflare Pages

1. Sube este proyecto a GitHub.
2. En Cloudflare Pages, crea proyecto nuevo desde ese repo.
3. Configura:
   - Framework: `Next.js`
   - Root directory: `frontend`
   - Build command: `npm run build`
   - Output directory: `.next`
4. Variable en Pages:
   - `NEXT_PUBLIC_API_URL=https://api.tudominio.com/api/v1`
5. Publica. Obtendras URL tipo `https://ridax.pages.dev`.

### 2) Backend gratis con Cloudflare Tunnel (desde tu PC)

Archivos incluidos para esto:

- `docker-compose.cloudflare.yml`
- `.env.cloudflare.example`
- `scripts/deploy-cloudflare.ps1`
- `scripts/update-cloudflare-backend.ps1`

Pasos:

1. Crea `.env.cloudflare` copiando `.env.cloudflare.example`.
2. Completa como minimo:
   - `SECRET_KEY`
   - `FRONTEND_URL`
   - `CORS_ORIGINS`
   - `CLOUDFLARE_TUNNEL_TOKEN`
3. Ejecuta despliegue:

```powershell
./scripts/deploy-cloudflare.ps1
```

4. En Cloudflare Tunnel, enruta un hostname (ej. `api.tudominio.com`) a `http://backend:8000`.

### 3) Telegram webhook (cuando tengas URL publica)

Con `api.tudominio.com` listo:

```powershell
./telegram-webhook.ps1 -Action set -Token "TU_TOKEN" -PublicBaseUrl "https://api.tudominio.com"
./telegram-webhook.ps1 -Action get -Token "TU_TOKEN"
```

## Futuras modificaciones desde tu PC local

Frontend:

- Haz cambios en `frontend/`, commit y push a GitHub.
- Cloudflare Pages despliega automaticamente.

Backend:

- Haz cambios en `backend/`.
- Publica cambios con:

```powershell
./scripts/update-cloudflare-backend.ps1
```

Esto evita trabajar doble: desarrollas local y actualizas internet con un comando.

## Endpoints clave del MVP

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `GET /api/v1/auth/me`
- `GET /api/v1/dashboard/summary`
- `GET/POST /api/v1/articles`
- `GET /api/v1/inventory`
- `POST /api/v1/inventory/adjust`
- `GET/POST /api/v1/sales`
- `GET/POST /api/v1/purchases`
- `GET /api/v1/reports/kpis`
- `GET /api/v1/reports/daily`
- `GET /api/v1/settings/roles`
- `GET /api/v1/settings/languages`
- `GET /api/v1/settings/currencies`
- `POST /api/v1/settings/currencies/convert`
- `GET /api/v1/settings/general`
- `PUT /api/v1/settings/general`
- `GET /api/v1/settings/users/preferences`
- `PUT /api/v1/settings/users/{user_id}/preferences`
- `POST /api/v1/integrations/telegram/webhook`
- `GET /api/v1/integrations/whatsapp/verify`
- `POST /api/v1/integrations/whatsapp/webhook`
- `GET /api/v1/public/catalog`

## Siguientes fases sugeridas

- Migraciones formales con Alembic.
- Refresco de token, politica de sesiones y 2FA opcional.
- Motor de reportes avanzado (export CSV/PDF).
- Checkout de e-commerce y pagos online.
- Gateway BFF para app movil.

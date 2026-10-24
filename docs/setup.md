# NEXORA — Setup Guide

## Quick Start (Docker)

```bash
cd nexora
cp .env.example .env   # edit secrets — see table below
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (dev only) | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

The department taxonomy installs automatically on first boot. Optional demo content is opt-in:

```bash
docker compose exec backend python scripts/seed.py --demo        # install
docker compose exec backend python scripts/seed.py --purge-demo  # remove
```

---

## Local Development (Without Docker)

You need MongoDB, Redis, Neo4j, and MonetDB running (via `docker compose up mongodb redis neo4j monetdb` or your own instances).

### Backend

```bash
cd nexora/backend
py -3.14 -m venv .venv          # Windows
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # edit secrets
uvicorn app.main:app --reload --port 8000
```

### Seed (optional demo data)

```bash
# From nexora/
python scripts/seed.py --taxonomy    # installs departments/subjects/topics (idempotent)
python scripts/seed.py --demo        # installs DEVELOPMENT DATA demo resources
python scripts/seed.py --purge-demo  # removes demo resources
```

### Frontend

```bash
cd nexora/frontend
npm install
npm run dev      # http://localhost:3000
```

---

## Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in the values marked **required**.

### Authentication

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `NEXORA_SECRET_KEY` | Production | auto-generated | `python -c "import secrets; print(secrets.token_urlsafe(48))"` — must be ≥32 bytes for HS256 |
| `NEXORA_ACCESS_TOKEN_MINUTES` | No | `30` | Access token lifetime |
| `NEXORA_REFRESH_TOKEN_DAYS` | No | `7` | Refresh token lifetime; ×4 with remember_me |
| `NEXORA_ADMIN_EMAIL` | No | — | Bootstrap admin account email |
| `NEXORA_ADMIN_PASSWORD` | No | — | Bootstrap admin account password |

### Databases

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXORA_MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `NEXORA_MONGO_DB` | `nexora` | Database name |
| `NEXORA_REDIS_URL` | `redis://localhost:6379` | Redis URL; blank → Redis disabled (cache/sessions degrade) |
| `NEXORA_NEO4J_URL` | `bolt://localhost:7687` | Neo4j bolt URI |
| `NEXORA_NEO4J_USER` | `neo4j` | |
| `NEXORA_NEO4J_PASSWORD` | `nexora_dev` | |
| `NEXORA_MONETDB_HOST` | `localhost` | |
| `NEXORA_MONETDB_PORT` | `50000` | |
| `NEXORA_MONETDB_DB` | `nexora` | |
| `NEXORA_MONETDB_USER` | `monetdb` | |
| `NEXORA_MONETDB_PASSWORD` | `monetdb` | |

### AI (RAG, overview, chat, semantic search)

| Variable | Required for AI | Notes |
|----------|----------------|-------|
| `NEXORA_AI_PROVIDER` | Yes | `openai` (default) · `anthropic` · `none` |
| `NEXORA_AI_API_KEY` | Yes (if provider ≠ none) | API key for the provider |
| `NEXORA_AI_BASE_URL` | No | Custom OpenAI-compatible endpoint (Groq, OpenRouter, Ollama at `http://localhost:11434/v1`, LM Studio) |
| `NEXORA_AI_MODEL` | No | Override model name (e.g. `gpt-4o-mini`, `claude-3-haiku-20240307`, `llama3`) |
| `NEXORA_AI_EMBED_MODEL` | No | Embedding model name |

Without a provider (`none`), AI endpoints return an honest "not configured" response. Search falls back to keyword + metadata ranking.

### YouTube

| Variable | Notes |
|----------|-------|
| `NEXORA_YOUTUBE_API_KEY` | YouTube Data API v3 key. Without it, video discovery reports "not configured". |

### Payments (Premium Resources)

| Variable | Notes |
|----------|-------|
| `NEXORA_PAYMENT_PROVIDER` | `stripe` · `none` (default). Without `stripe`, premium resources show price but the unlock button reports "payment provider not configured" — never fakes success. |
| `NEXORA_STRIPE_SECRET_KEY` | Stripe secret key (`sk_test_…` for development) |
| `NEXORA_STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_…`) |
| `NEXORA_PREMIUM_DEFAULT_PRICE_USD` | `4.99` | Default price when resource has no explicit price |

### Email (Password Reset)

| Variable | Notes |
|----------|-------|
| `NEXORA_SMTP_HOST` | SMTP server hostname |
| `NEXORA_SMTP_PORT` | Default `587` |
| `NEXORA_SMTP_USER` | SMTP auth username |
| `NEXORA_SMTP_PASSWORD` | SMTP auth password |
| `NEXORA_SMTP_FROM` | From address |

In development without SMTP, the reset token prefix (first 8 chars only) is written to the server log. In production without SMTP, no token is logged at all (but no email is sent either — configure SMTP for production).

### Rate Limiting

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXORA_RATE_LIMIT_REQUESTS` | `120` | Global requests per window per identity |
| `NEXORA_RATE_LIMIT_WINDOW_SECONDS` | `60` | Global window |
| `NEXORA_AUTH_RATE_LIMIT_REQUESTS` | `10` | Auth endpoints only (login, register, reset) |
| `NEXORA_AUTH_RATE_LIMIT_WINDOW_SECONDS` | `300` | Auth window (5 minutes) |

### Ingestion Sync

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXORA_SYNC_ENABLED` | `true` | Enable background sync |
| `NEXORA_SYNC_INTERVAL_MINUTES` | `60` | Sync interval |
| `NEXORA_MAX_RESOURCES_PER_RUN` | `200` | Cap per source per run |

### Other

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXORA_ENVIRONMENT` | `development` | `development` · `staging` · `production` |
| `NEXORA_DEBUG` | `false` | Enable debug logging |
| `NEXORA_FRONTEND_URL` | `http://localhost:3000` | Used for payment redirect URLs |
| `NEXORA_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `NEXORA_TRUST_PROXY_HEADERS` | `false` | Trust `X-Forwarded-For` (set `true` behind a reverse proxy) |

---

## Degraded Boot Behaviour

NEXORA can start even when databases are partially unavailable:

| Database down | Effect |
|---------------|--------|
| **MongoDB** | API starts in degraded mode (`/health` only). A background task retries every 15 s. Once MongoDB recovers, the app becomes fully operational without restart. |
| **Redis** | Rate limiting falls back to in-process. Sessions fall back to MongoDB mirror. Caches show cold misses. |
| **Neo4j** | Knowledge graph features degrade (related resources, graph navigation). Everything else works. |
| **MonetDB** | Analytics events buffer in memory (up to 5,000). Admin analytics shows stale/unavailable data. |

All databases report their status at `GET /health` and `GET /api/admin/databases`.

---

## Troubleshooting

**`MongoDB is required for NEXORA to operate` at startup**  
MongoDB was not reachable within the boot retry window. Check `NEXORA_MONGO_URL` and that the MongoDB container/service is running.

**`TypeError: Logger._log() got an unexpected keyword argument`**  
This was a bug in `StructuredLogger.process()` fixed in the security-hardening pass. Ensure you have the latest `app/core/logging.py`.

**Rate limit errors on login during development**  
The auth rate limiter is stricter (10 req / 5 min per IP). In tests without Redis, it falls back to in-process; the limits still apply.

**AI features return "not configured"**  
Expected when `NEXORA_AI_PROVIDER=none` or no `NEXORA_AI_API_KEY` is set. Set the env vars and restart.

**Stripe webhook not verifying**  
Ensure `NEXORA_STRIPE_WEBHOOK_SECRET` matches the secret from your Stripe dashboard webhook settings. Use the Stripe CLI for local testing: `stripe listen --forward-to localhost:8000/api/payments/webhook/stripe`.

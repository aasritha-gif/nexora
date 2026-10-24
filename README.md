# NEXORA

> **Your Knowledge. One Intelligent Universe.**

An AI-powered academic library and knowledge discovery platform: a digital universe
where students discover, search, read, research, and learn from academic resources
using intelligent technology.

NEXORA combines a digital library, an academic search engine, a research discovery
portal, personalized learning, an AI reading assistant, a resource-specific AI tutor,
video learning discovery, and academic analytics — on a polyglot NoSQL architecture.

---

## Stack

| Layer      | Technology                                      |
|------------|--------------------------------------------------|
| Frontend   | Next.js (App Router) · React · TypeScript · Tailwind CSS |
| Backend    | FastAPI · Python · Pydantic · JWT auth           |
| Documents  | **MongoDB** — users, resources, reviews, flexible metadata (canonical store) |
| Cache      | **Redis** — sessions, search/result caching, trending, rate limiting, TTL state |
| Graph      | **Neo4j** — knowledge universe: Department→Subject→Topic→Resource, authors, related-to, user activity |
| Analytics  | **MonetDB** — columnar analytical store: views/reads/searches, popularity, trends, ingestion stats |
| AI         | RAG (chunking → embeddings → hybrid retrieval) behind a provider-agnostic layer (OpenAI-compatible / Anthropic / Ollama, selected via config) |
| Ingestion  | Modular source adapters: arXiv · Open Library · Crossref · DOAJ · YouTube (key-gated) |

## Quick start (Docker)

```bash
cd nexora
cp .env.example .env          # then edit secrets (see table below)
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

The department taxonomy installs itself on first boot — registration and
ingestion classification depend on it. Optional sample content is opt-in, is
labelled `DEVELOPMENT DATA` everywhere it appears, and can be removed completely:

```bash
docker compose exec backend python scripts/seed.py --demo        # install
docker compose exec backend python scripts/seed.py --purge-demo  # remove
```

Live ingestion from arXiv/Open Library/Crossref/DOAJ
runs on the sync worker (no API keys required for those sources).

## Local development (without Docker)

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# optional: development corpus (from the repo root)
python scripts/seed.py --demo

# frontend
cd frontend
npm install
npm run dev
```

Databases must be reachable (via `docker compose up mongodb redis neo4j monetdb`
or your own instances). The backend boots even when some databases are down —
they appear as `DEGRADED` in `/health` and dependent features degrade honestly.

## Tests

```bash
cd backend
pytest            # unit + contract suite (no databases required)
```

The suite covers the security-critical pure logic — password hashing, JWT
issuance/validation (type confusion, expiry, tampering, issuer), MonetDB SQL
guards (literal rendering, identifier/event allowlists), dedup fingerprints and
metadata merging, rule classification, taxonomy referential integrity, rate
limiting, error-handler responses, and API router composition. Integration
tests against live databases run inside Docker Compose (see `docs/testing.md`).

## Required configuration (`.env`)

| Variable | Required for | Notes |
|---|---|---|
| `NEXORA_SECRET_KEY` | auth (prod) | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `NEXORA_AI_PROVIDER` + `NEXORA_AI_API_KEY` (+ `NEXORA_AI_BASE_URL`, `NEXORA_AI_MODEL`) | AI Overview / AI Reading / AI Chat / semantic search | `openai` accepts any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, Ollama at `http://localhost:11434/v1`, LM Studio); `anthropic` for Claude; unset (`none`) → AI endpoints return an explicit "not configured" state, search falls back to keyword+metadata ranking |
| `NEXORA_YOUTUBE_API_KEY` | video discovery | YouTube Data API v3 key; without it the video module reports "not configured" |
| `NEXORA_STRIPE_SECRET_KEY` + `NEXORA_PAYMENT_PROVIDER=stripe` | premium purchases | Without a provider, premium resources show price but the unlock action reports "payment provider not configured" (never fake success) |
| `NEXORA_SMTP_*` | password-reset email | In development without SMTP, the reset link is written to the server log only |

All four databases, Crossref polite-pool mailto, and sync intervals are configured
in the same file — see `.env.example` for the full annotated list.

## Repository layout

```
nexora/
├── frontend/        Next.js app (App Router, components, hooks, types)
├── backend/
│   ├── app/
│   │   ├── api/         HTTP routes (auth, resources, search, ingestion, ai, admin, …)
│   │   ├── schemas/     Pydantic request/response models
│   │   ├── models/      document shapes (users, resources, reviews, taxonomy, …)
│   │   ├── services/    business logic:
│   │   │                  search_service.py  – query parsing, ranking, semantic search
│   │   │                  ai_service.py      – AI overview / reading / chat / RAG
│   │   │                  auth_service.py    – registration, login, sessions
│   │   │                  ingestion.py       – pipeline orchestration
│   │   │                  recommendation.py  – personalised feed
│   │   │                  resource_service.py – resource hydration, homepage feed
│   │   │                  youtube_service.py  – YouTube discovery
│   │   │                  discovery.py       – cross-source discovery entry point
│   │   ├── repositories/ data-access layer (Mongo, Neo4j, MonetDB, Redis queries)
│   │   ├── databases/   adapters + health monitoring for the 4 databases
│   │   ├── ingestion/   source adapters (arXiv, Open Library, Crossref, DOAJ, YouTube),
│   │   │                  classifier, dedup, pipeline
│   │   ├── ai/          provider.py – LLM provider abstraction (OpenAI-compat/Anthropic/Ollama)
│   │   ├── payments/    provider.py – payment provider abstraction (Stripe / none)
│   │   ├── seed/        taxonomy_data.py, demo_data.py, runner.py
│   │   └── core/        config, logging, security, errors, rate limiting
│   └── tests/           unit + contract tests (no live databases required)
├── docker/          Dockerfiles
├── scripts/         dev + ops scripts (seed.py, verify_e2e.py)
└── docs/            architecture, setup, security, ingestion, testing
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system design, data flow, database responsibilities
- [`docs/setup.md`](docs/setup.md) — environment setup, full `.env` table, troubleshooting
- [`docs/security.md`](docs/security.md) — auth model, RBAC, rate limiting, secrets policy
- [`docs/ingestion.md`](docs/ingestion.md) — source adapters, classification rules, dedup, sync
- [`docs/testing.md`](docs/testing.md) — how to run tests, what is covered, live DB integration tests

## Principles

1. **No fake functionality.** Unconfigured integrations say so — clearly — at the API and UI level.
2. A resource exists **once** (`RES-000001`): a document in MongoDB, relationships in Neo4j, analytics rows in MonetDB, a cached representation in Redis — each database serves its own purpose.
3. Resources are **discovered automatically** from legitimate open sources; restricted resources are metadata + external link only.
4. **DEVELOPMENT DATA** seed records are labelled as such and never presented as discovered content.

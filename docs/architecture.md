# NEXORA — Architecture

## System Overview

NEXORA is a polyglot NoSQL academic resource platform. A single logical resource (e.g. `RES-000001`) lives across four databases simultaneously, each serving a distinct purpose:

```
                          NEXORA
                            │
                            ▼
                     WEB APPLICATION
                    (Next.js / React)
                            │
                            ▼
                       API GATEWAY
                    (FastAPI / Python)
                            │
         ┌──────────────────┼───────────────────┐
         │                  │                   │
         ▼                  ▼                   ▼
    AUTH SERVICE      RESOURCE SERVICE     SEARCH SERVICE
         │                  │                   │
         └──────────────────┼───────────────────┘
                            │
                            ▼
                   RESOURCE INGESTION
                            │
                            ▼
                  VALIDATION + CLASSIFY
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
         MongoDB          Neo4j          MonetDB
        Documents       Knowledge       Analytics
                            Graph
             │
             ▼
           Redis
           Cache
                            │
                            ▼
                     SEARCH / RANKING
                            │
                            ▼
                     RAG / AI LAYER
                            │
           ┌────────────────┼─────────────────┐
           ▼                ▼                 ▼
      AI Overview      AI Reading        AI Chatbot
```

---

## Database Responsibility Split

The four-database architecture is **not** redundant storage. Each database has a distinct, non-overlapping purpose.

### MongoDB — Canonical Document Store

**Role:** The source of truth for all application-level data.

Stores:
- Users, credentials, roles, profile data
- Resource documents (title, authors, metadata, taxonomy, stats)
- Reviews, bookmarks, reading history
- Sessions mirror (fallback when Redis is down)
- Ingestion run logs and retry queue
- AI overviews, resource chunks, chat messages, user notes, flashcards
- Password reset tokens
- Purchase records

**A resource lives here once, completely.** All other databases reference it by `resource_id`.

### Redis — Cache, Sessions, Rate Limiting

**Role:** Speed layer, not storage. All data here is ephemeral and can be lost without data corruption.

Stores with TTL:
- Access tokens are **not** stored — they are stateless JWTs. Refresh token sessions are stored as `session:{user_id}:{jti}` with the token fingerprint (SHA-256) as value
- Search result caches (2-minute TTL default)
- Homepage and resource detail caches
- YouTube discovery results (6-hour TTL)
- AI response caches
- Trending resource sorted sets
- Rate limiter counters (`rl:{identity}:{window}`)
- Auth rate limiter counters (`rl:auth:{ip}:{window}`)
- Stripe webhook dedup keys (`stripe:event:{event_id}`, 24-hour TTL)

**Redis outage:** the system degrades gracefully — rate limiting falls back to in-process, sessions fall back to MongoDB mirror, caches show misses. **No data is lost.**

### Neo4j — Knowledge Graph

**Role:** Relational structure and discovery.

Node types: `Department`, `Subject`, `Topic`, `Resource`, `Author`, `User`, `Source`

Relationships:
```
Department -[:CONTAINS]->       Subject
Subject    -[:HAS_TOPIC]->      Topic
Topic      -[:HAS_RESOURCE]->   Resource
Department -[:HAS_RESOURCE]->   Resource
Resource   -[:WRITTEN_BY]->     Author
Resource   -[:DISCOVERED_FROM]->Source
User       -[:STUDIES]->        Department
User       -[:VIEWED]->         Resource
User       -[:BOOKMARKED]->     Resource
User       -[:RATED]->          Resource
```

Used for: "Related Resources" (graph neighbours), knowledge universe visualisation, department→subject→topic→resource navigation, author pages, recommendation traversal.

**All writes are idempotent MERGE operations.** The ingestion pipeline and sync jobs can replay safely.

### MonetDB — Columnar Analytics

**Role:** Analytical queries that would be slow or inappropriate in MongoDB.

Tables:
- `resource_events` — one row per view/read/download/search event; columns: `event_time`, `event_type`, `resource_id`, `user_id`, `department_code`, `subject_code`, `search_query`, `result_count`

Queries served:
- Top resources by department, subject, type, time window
- Search query popularity
- User activity over time
- Admin overview statistics
- Trending resource computation

Events are **buffered in memory** (threshold: 25 events or 20 s interval) and batch-inserted. If MonetDB is down, events queue to a 5,000-row cap; they are flushed when the adapter recovers.

---

## Request Data Flow

### Anonymous Search Request

```
1. Browser → GET /api/search?q=…&department=CS&type=book
2. CORS middleware → observability middleware → bearer auth middleware (no token, passes)
3. enforce_rate_limit dependency: check Redis counter for client IP
4. SearchService.search():
   a. interpret() — NLP pre-processing, type/difficulty/year hints
   b. Cache lookup → Redis (key: hash of filters + page)
   c. MISS: ResourceRepository.text_candidates() → MongoDB $text search
   d. Re-rank (popularity × recency × relevance score)
   e. Optional semantic re-rank if AI provider is configured
   f. Store in Redis cache (TTL: 120 s)
   g. Record search event → AnalyticsRepository (MonetDB buffer)
5. Response: SearchResponse (paginated, max 50/page)
```

### Resource Ingestion (Automated)

```
SOURCE (arXiv / Open Library / Crossref / DOAJ / YouTube)
  ↓
DiscoveredItem produced by source adapter
  ↓
DedupEngine: check DOI → ISBN → arXiv ID → source_id → URL → fingerprint
  ↓ (no duplicate found)
RuleClassifier: keyword votes against taxonomy → department, subject, topic, difficulty
  ↓
Resource model built + resource_id generated (RES-XXXXXX)
  ↓
MongoDB: insert full document
  ↓
Neo4j: MERGE Resource node + relationships (parallel, non-blocking on failure)
  ↓
MonetDB: record ingestion event (buffered)
  ↓
Redis: cache invalidation for affected department/subject keys
  ↓
Search index: MongoDB text index automatically includes new document
```

### AI Resource Chat

```
User question → POST /api/ai/chat/{resource_id}
  ↓
AIService: load resource, retrieve pre-computed chunks from MongoDB
  ↓
Embed question → vector similarity search over chunk embeddings
  ↓
Top-k relevant chunks assembled as context
  ↓
LLM call (provider-agnostic: OpenAI / Anthropic / Ollama)
  ↓
Answer + chunk references returned
  ↓
Chat message persisted to MongoDB (resource_id + user_id scope)
```

---

## API Module Map

| Prefix | Module | Responsibility |
|--------|--------|----------------|
| `/auth` | `routes/auth.py` | Register, login, refresh, logout, password reset |
| `/api/resources` | `routes/resources.py` | Resource CRUD, homepage feed, department browse |
| `/api/search` | `routes/search.py` | Unified search, semantic search |
| `/api/taxonomy` | `routes/taxonomy.py` | Departments, subjects, topics, knowledge graph |
| `/api/engagement` | `routes/engagement.py` | Bookmarks, reading history, reviews, ratings |
| `/api/ai` | `routes/ai.py` | AI overview, AI reading, resource chat |
| `/api/youtube` | `routes/youtube.py` | Video and playlist discovery |
| `/api/ingestion` | `routes/ingestion.py` | Trigger sync, source management |
| `/api/payments` | `routes/payments.py` | Checkout, Stripe webhook |
| `/api/analytics` | `routes/analytics.py` | Usage analytics |
| `/api/admin` | `routes/admin.py` | User management, database health, system info |
| `/api/users` | `routes/users.py` | User profile, library |
| `/health` | `routes/health.py` | Liveness + readiness probes |

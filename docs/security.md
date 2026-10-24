# NEXORA — Security Model

## Authentication

### JWT Access Tokens

- **Format:** HS256-signed JWT with claims `sub` (user_id), `role`, `jti`, `iss` (`nexora`), `iat`, `exp`, `type` (`access`)
- **Lifetime:** configurable via `NEXORA_ACCESS_TOKEN_MINUTES` (default 30 min)
- **Stateless:** access tokens are not stored. They are verified by signature + expiry on every request.
- **Role:** the `role` claim in the token is a **hint for routing**. MongoDB is always consulted for the live account state (`is_active`, `tokens_invalid_before`). A role change or deactivation takes effect at the next request, regardless of token lifetime.

### Refresh Tokens

- **Format:** HS256-signed JWT with `type: refresh` and a unique `jti`
- **Storage:** only a SHA-256 fingerprint of the refresh token is stored in Redis (`session:{user_id}:{jti}` → fingerprint) and mirrored in MongoDB `sessions`. The raw token is never persisted.
- **Rotation:** every use of a refresh token creates a new session and revokes the old one (refresh token rotation).
- **Revocation:** calling `/auth/logout` deletes the Redis key and marks the MongoDB session revoked. `/auth/logout-all` revokes all sessions for the user and sets `tokens_invalid_before` on the user document, instantly invalidating all access tokens regardless of their remaining lifetime.

### `tokens_invalid_before`

Every access token contains `iat` (issued-at). `AuthService.resolve_access_token()` checks `user.tokens_invalid_before`: if the token was minted before this timestamp, it is rejected even if the signature and expiry are valid. This allows instant global invalidation after a password change, role change, or admin-triggered logout-all.

---

## RBAC (Role-Based Access Control)

Three roles: `student` (default for self-service registration) · `faculty` · `admin`

| Action | Student | Faculty | Admin |
|--------|---------|---------|-------|
| Browse, search, read | ✅ | ✅ | ✅ |
| Bookmark, review, rate | ✅ | ✅ | ✅ |
| AI features (if configured) | ✅ | ✅ | ✅ |
| Purchase premium resources | ✅ | ✅ | ✅ |
| Trigger ingestion sync | ❌ | ❌ | ✅ |
| Manage users, resources, sources | ❌ | ❌ | ✅ |
| View admin dashboard, analytics | ❌ | ❌ | ✅ |
| Monitor database health | ❌ | ❌ | ✅ |
| Change any user's role | ❌ | ❌ | ✅ |

**Self-service registration always creates a `student` account.** The `RegisterRequest` schema has no `role` field. Role elevation requires direct admin action via `PATCH /api/admin/users/{user_id}/role`.

---

## Rate Limiting

NEXORA operates two independent rate limiters:

### Global Rate Limiter

- Scope: all `/api/*` routes
- Identity: `user:{user_id}` for authenticated requests; `ip:{ip}` for anonymous
- Default: 120 requests per 60 seconds
- Configured via: `NEXORA_RATE_LIMIT_REQUESTS` / `NEXORA_RATE_LIMIT_WINDOW_SECONDS`

### Auth Rate Limiter (Stricter)

Applied **only** to the four anonymous credential endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/forgot-password`, `POST /auth/reset-password`.

- Identity: `auth:{client_ip}` — always per-IP because these routes are unauthenticated
- Default: **10 requests per 300 seconds (5 minutes)**
- Configured via: `NEXORA_AUTH_RATE_LIMIT_REQUESTS` / `NEXORA_AUTH_RATE_LIMIT_WINDOW_SECONDS`
- Separate `RateLimiter` instance (not shared with the global limiter)

### Per-Account Login Lockout

In addition to the IP-based auth rate limiter, `AuthService` tracks consecutive failed login attempts **per identifier** (email or student ID) in memory:

- After **5 consecutive failures**, the account is locked for **300 seconds**
- A successful login resets the counter for that identifier
- The in-memory map is bounded to 10,000 entries; entries that are no longer locked are evicted when the cap is reached

**Defence in depth:** the IP-based auth limiter catches distributed attacks; the per-account lockout catches targeted credential-stuffing against specific accounts.

---

## Password Handling

- **Hashing:** bcrypt via `passlib`. Work factor is bcrypt default.
- **Storage:** the `password_hash` field carries `Field(exclude=True)` in Pydantic — it is automatically excluded from any `model_dump()` call, making it impossible to accidentally leak via a generic serialisation path.
- **Verification:** `verify_password()` catches `ValueError` from malformed hashes and returns `False` instead of raising (prevents oracle attacks on invalid hash formats).

---

## Password Reset Token Policy

- Reset tokens are short-lived JWTs (30 minutes, `type: password_reset`).
- Only a SHA-256 fingerprint of the token is stored in MongoDB `password_resets`. The raw token never persists.
- Token logging policy:
  - **Development / non-production:** if SMTP is not configured, only the first 8 characters of the token are logged (enough for correlation, not enough to use).
  - **Production:** if SMTP is not configured, a warning is logged with no token fragment whatsoever.
  - A live SMTP sender sends the full token only inside the email body, never to logs.

---

## Payment Trust Boundary

The Stripe webhook handler enforces three independent checks:

1. **Signature verification** — HMAC-SHA256 + `compare_digest` + 300 s tolerance (via Stripe library). Any tampered or unsigned payload is rejected before any state change.

2. **Replay deduplication** — Stripe event IDs are stored in Redis with `SET NX` (24-hour TTL). A duplicate delivery returns `{"received": true, "duplicate": true}` immediately. If Redis is unavailable, the event is processed anyway (mark_paid / mark_refunded are idempotent) and a warning is logged.

3. **Amount verification** — before marking a purchase paid, the handler loads the pending purchase from MongoDB and compares `purchase.amount_usd` (what we priced) to `session.amount_total / 100` (what Stripe collected). A mismatch causes a warning log and the purchase is **not** marked paid. This prevents a client-manipulated price from granting access. If `amount_total` is absent (older payload), the check is skipped for backwards compatibility.

---

## Secret Handling Policy

- No credentials are ever hard-coded in source code.
- All secrets come from environment variables (`.env` file in development, secrets manager in production).
- The `safe_summary()` method on `Settings` explicitly whitelists what appears in logs — connection strings, API keys, and passwords are excluded.
- Internal error stack traces are never returned to API clients. The exception handler returns `{"error": {"code": ..., "message": ...}}` only.
- CORS is explicitly configured; only origins in `NEXORA_CORS_ORIGINS` are allowed.

---

## Input Validation

- All request bodies validated by Pydantic with field constraints (min/max length, regex patterns, value ranges).
- MongoDB queries use driver parameter binding — no string interpolation.
- MonetDB: all dynamic values pass through `sql_lit()` after shape validation by `validate_id()`, `validate_code()`, or `validate_event_type()` (allowlist + regex `^[A-Za-z0-9_\-:.]{1,64}$`). Column names are compile-time constants, never user-supplied.
- Neo4j: all queries use parameterised Cypher. User data is always a parameter value, never part of the query string.
- Redis: cache keys are constructed from server-side values only (user_id, resource_id, request hashes). User input is never placed directly in a Redis key.
- Regex inputs in MongoDB queries (`$regex` for author search) are escaped via `_escape()`.
- File uploads: validated by content type + size limits (enforced at route level).

---

## API Security Headers

- `X-Request-ID` is echoed from the client (stripped of non-alphanumeric characters, capped at 64 chars) or generated server-side. It appears in every log line for that request.
- CORS headers are set by `CORSMiddleware` with explicit `allow_origins` list.
- OpenAPI documentation (`/docs`, `/openapi.json`) is **disabled in production** (`NEXORA_ENVIRONMENT=production`).

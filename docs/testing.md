# NEXORA — Testing Strategy

## Overview

The NEXORA backend includes a comprehensive automated test suite designed with clean architecture principles. It separates pure unit/contract testing from live polyglot database integration tests.

---

## Running Unit & Contract Tests

All unit and API contract tests run **completely without external database dependencies** using in-memory fakes and strict dependency injection.

### Execution

```bash
cd nexora/backend
.\.venv\Scripts\python.exe -m pytest -v
```

### Pytest Configuration

Configured in `nexora/backend/pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-q"
```

---

## Test Suite Structure

The suite covers 138+ automated tests:

| Test File | Focus Area |
|-----------|------------|
| `test_security_fixes.py` | Role lockdown (student default), credential log safety, per-account brute-force lockout, dedicated auth rate limiter (`auth:` namespace), Stripe webhook dedup & price tamper checks. |
| `test_security.py` | Passwords (bcrypt hashing & malformed hash guards), JWT token minting/decoding, type confusion prevention, expiry checks, replay detection. |
| `test_api_contract.py` | Route inclusion, method-path dedup, taxonomy routes at root, dependency bindings. |
| `test_classifier.py` | Deterministic keyword voting, department/subject/topic confidence floors (0.25) and ceilings (0.95), difficulty regex hints. |
| `test_dedup.py` | Title & author fingerprinting, identifier hierarchy (DOI > ISBN > arXiv > source_id > URL), metadata merge rules. |
| `test_errors.py` | Structured error mapping, status codes, consistent JSON payload formats (`{"error": {"code", "message"}}`). |
| `test_models.py` | Pydantic model validation, serialization exclusion (`password_hash`), type coercions. |
| `test_monetdb_guards.py` | Column and identifier whitelisting, SQL literal injection protection via `sql_lit`, regex validation of event names. |
| `test_rate_limit.py` | In-memory fallback sliding window, Redis pipeline execution, window sliding, threshold bounds. |
| `test_taxonomy_data.py` | Department/subject/topic hierarchy integrity, code uniqueness, cycle-free relationships. |
| `test_config.py` | Settings parsing, production secret key length enforcement, safe log summaries. |

---

## Integration Tests with Live Databases

Integration tests that verify cross-database transactions across all four databases (MongoDB, Neo4j, MonetDB, Redis) require live daemon instances:

```
Resource Ingestion
   ↓
MongoDB (Document) ──→ Neo4j (Graph) ──→ MonetDB (Analytics) ──→ Redis (Cache)
```

### Running with Docker Compose

When Docker is available on the deployment host:

```bash
cd nexora
docker compose up -d mongodb redis neo4j monetdb
docker compose run --rm backend pytest tests/integration
```

### End-to-End Verification Script

For verifying the running stack (after starting Docker Compose), run the standalone verification script:

```bash
python nexora/scripts/verify_e2e.py
```
This script exercises real HTTP endpoints from health monitoring and authentication to search, bookmarking, AI status, and admin RBAC checks.

# NEXORA — Ingestion Pipeline

## Overview

The ingestion engine automatically discovers academic resources from legitimate, configured open sources. It ensures deduplication, normalisation, automated taxonomy classification, and fan-out persistence across MongoDB, Neo4j, MonetDB, and Redis.

```
SOURCE (Open API / Repository)
  ↓
ADAPTER (DiscoveredItem)
  ↓
VALIDATION & NORMALISATION
  ↓
DUPLICATE DETECTION (Identifer Priority + Title/Author Fingerprint)
  ↓
CLASSIFICATION (RuleClassifier against Taxonomy)
  ↓
RESOURCE ID GENERATION (RES-000001)
  ↓
FAN-OUT PERSISTENCE:
  ├── MongoDB (canonical document + search text index)
  ├── Neo4j (graph nodes & relationships)
  ├── MonetDB (ingestion & resource events buffer)
  └── Redis (cache eviction / invalidation)
```

---

## Source Adapters

All source adapters inherit from `SourceAdapter` and yield `DiscoveredItem` records:

| Source | Adapter | Resource Types | Authentication | Full Text |
|--------|---------|----------------|----------------|-----------|
| **arXiv** | `ArxivAdapter` | Research papers | None (Public API) | Abstract + Open PDF link |
| **Open Library** | `OpenLibraryAdapter` | Books, E-books | None (Public API) | Covers, preview/borrow URLs |
| **Crossref** | `CrossrefAdapter` | Journal articles, papers | Polite-pool email | Metadata, publisher links, DOI |
| **DOAJ** | `DOAJAdapter` | Open access journals/articles | None (Public API) | Open-access links, full-text URLs |
| **YouTube** | `YouTubeSourceAdapter` | Educational videos/playlists | `NEXORA_YOUTUBE_API_KEY` | Video metadata, duration, channels |

> **Ethical & Legal Compliance:** The ingestion engine never scrapes prohibited content or bypasses paywalls. For restricted/proprietary publications, NEXORA indexes metadata, abstract, and external canonical URLs sending the user directly to the legitimate publisher.

---

## Deduplication Strategy

To prevent redundant or duplicate entries, incoming items pass through `DedupEngine` before creation:

### 1. Strong Identifiers (Priority Order)
Items are checked against existing MongoDB indexes in strict priority:
1. **DOI** (`identifiers.doi`)
2. **ISBN** (`identifiers.isbn`)
3. **arXiv ID** (`identifiers.arxiv_id`)
4. **Source ID** (`identifiers.source_id`, formatted as `{source_key}:{id}`)
5. **Canonical URL** (`identifiers.url`)

### 2. Title & Author Fingerprinting
When strong identifiers are missing or unindexed, a cryptographic fingerprint is generated:
- Normalized title (lowercase, bracket/punctuation-stripped, token-sorted)
- Cleaned first author surname (excluding terms like "unknown", "editor", "staff")
- SHA-1 hash: `hashlib.sha1(normalized_title + "|" + first_author_key).hexdigest()`

### 3. Metadata Merging
When an existing resource is re-discovered from another source, metadata is merged rather than duplicated:
- Descriptions, publisher, and year fill in missing fields.
- Higher citation counts supersede lower values.
- Keywords and alternative subjects are unioned.

---

## Classification Engine

`RuleClassifier` automatically assigns incoming resources to the university taxonomy based on text voting across titles, abstracts, and keywords:

- **Department / Subject / Topic Voting:**
  - Token-level matching against department, subject, and topic definitions and pre-configured synonyms.
  - Frequency and field-weighted score calculation.
  - Confidence scoring bounded between **floor `0.25`** and **ceiling `0.95`**.
- **Difficulty:**
  - Detected using regex patterns (`_BEGINNER_RE`, `_ADVANCED_RE`).
  - Defaults to `INTERMEDIATE` when ambiguous.
- **Academic Level:**
  - Classified into `UNDERGRADUATE`, `POSTGRADUATE`, or `RESEARCH`.
- **Admin Overrides:**
  - Admins can edit or correct taxonomy classifications via `PATCH /api/admin/resources/{id}/classification`. Admin-assigned classifications are permanent and protected against sync overwrite.

---

## Synchronization & Scheduling

- Ingestion sync jobs run periodically according to source-level `schedule_minutes` (configured via `DEFAULT_SOURCES` or updated in admin settings).
- **Run Status & Monitoring:**
  - Sync metrics (`resources_discovered`, `resources_added`, `duplicates_skipped`, `failures`) are tracked in `ingestion_runs`.
  - Available to admins via `GET /api/admin/ingestion/runs` and `GET /api/admin/ingestion/sources`.
- **Retry Mechanism:**
  - Failed secondary sync operations (e.g. Neo4j connectivity drop during MongoDB insert) push a task to `ingestion_retry_queue` with exponential backoff up to 5 attempts.

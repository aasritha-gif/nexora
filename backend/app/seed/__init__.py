"""Seed data for NEXORA.

Two kinds of data live here and they are deliberately separate:

* `taxonomy_data` — the canonical academic structure (departments, subjects,
  topics). This is reference data, not demo data: registration validates a
  department against it, the ingestion classifier votes against it, and the
  knowledge graph is built from it. It ships with the product.

* `demo_data` — illustrative users and resources so an empty install is not an
  empty screen. Every document is flagged `is_seed_data=True` and carries a
  `DEVELOPMENT DATA` label, and `runner.purge_demo()` removes it completely.
"""

from __future__ import annotations

from app.seed.runner import SeedReport, purge_demo, seed_all, seed_demo, seed_taxonomy

__all__ = ["SeedReport", "purge_demo", "seed_all", "seed_demo", "seed_taxonomy"]

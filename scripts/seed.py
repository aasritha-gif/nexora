#!/usr/bin/env python
"""NEXORA seed CLI.

    python scripts/seed.py                 # taxonomy + demo corpus
    python scripts/seed.py --taxonomy      # reference data only (safe for prod)
    python scripts/seed.py --demo          # demo corpus only
    python scripts/seed.py --purge-demo    # remove every DEVELOPMENT DATA record

Seeding is idempotent: re-running converges on the same state instead of
duplicating. `--taxonomy` installs reference data the application needs to
function; `--demo` installs illustrative records that are flagged
`is_seed_data` and removable with `--purge-demo`.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent / "backend"
_CONTAINER_ROOT = _HERE.parent

if (_BACKEND / "app").is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
elif (_CONTAINER_ROOT / "app").is_dir() and str(_CONTAINER_ROOT) not in sys.path:
    sys.path.insert(0, str(_CONTAINER_ROOT))

from app.api.dependencies import AppState  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.databases import Databases  # noqa: E402
from app.seed import SeedReport, purge_demo, seed_all, seed_demo, seed_taxonomy  # noqa: E402
from app.seed.demo_data import DEMO_PASSWORD, DEMO_USERS  # noqa: E402

_LABELS = {
    "departments": "departments",
    "subjects": "subjects",
    "topics": "topics",
    "graph_taxonomy_nodes": "graph taxonomy nodes",
    "graph_resources": "graph resources",
    "users_created": "users created",
    "users_existing": "users already present",
    "resources_created": "resources created",
    "resources_updated": "resources updated",
    "chunks": "text chunks indexed",
    "bookmarks": "bookmarks",
    "views": "reading history entries",
    "reviews": "reviews",
    "analytics_events": "analytics events",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed.py", description="Seed NEXORA taxonomy and development data."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--taxonomy", action="store_true",
        help="seed departments, subjects and topics only (reference data)",
    )
    group.add_argument("--demo", action="store_true", help="seed the development corpus")
    group.add_argument(
        "--all", action="store_true", help="seed taxonomy and demo data (default)"
    )
    group.add_argument(
        "--purge-demo", action="store_true",
        help="delete every record flagged as development data",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="skip the confirmation prompt for --purge-demo"
    )
    return parser.parse_args(argv)


def _print_report(report: SeedReport) -> None:
    counts = report.counts()
    print("\nSeeded:")
    if not counts:
        print("  nothing to do — database already up to date")
    for key, value in counts.items():
        print(f"  {_LABELS.get(key, key):<28} {value}")

    for warning in report.warnings:
        print(f"\n  ! {warning}")


def _print_demo_accounts(report: SeedReport) -> None:
    if not (report.users_created or report.users_existing):
        return
    print(f"\nDevelopment accounts — password: {DEMO_PASSWORD}")
    print("  (these credentials only ever exist in a local development database)")
    for email, student_id, name, role, department, _year, _semester in DEMO_USERS:
        print(f"    {email:<28} {role:<8} {department:<8} {student_id}")


def _print_purge(removed: dict[str, int]) -> None:
    print("\nRemoved:")
    if not any(removed.values()):
        print("  nothing to remove — no development data found")
        return
    for key, value in removed.items():
        if value:
            print(f"  {key:<28} {value}")


def _confirm() -> bool:
    answer = input(
        "\nThis deletes all users, resources, engagement and analytics rows flagged\n"
        "as development data. Taxonomy is kept. Continue? [y/N] "
    )
    return answer.strip().lower() in {"y", "yes"}


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.debug)

    if args.purge_demo and not args.yes and not _confirm():
        print("Aborted.")
        return 1

    databases = Databases(settings)
    await databases.startup()
    try:
        state = AppState(settings, databases)
    except RuntimeError as exc:
        print(f"\nCannot seed: {exc}", file=sys.stderr)
        await databases.shutdown()
        return 1

    try:
        if args.purge_demo:
            _print_purge(await purge_demo(state))
            return 0

        if args.taxonomy:
            report = await seed_taxonomy(state)
        elif args.demo:
            report = await seed_demo(state)
        else:
            report = await seed_all(state)

        _print_report(report)
        _print_demo_accounts(report)
        return 0
    finally:
        await state.close()
        await databases.shutdown()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

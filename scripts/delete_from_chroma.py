"""
Delete chunks from ChromaDB by page title.

Examples:
    python -m scripts.delete_from_chroma --page-title "Terraria Boss Progression Roadmap" --all-collections --dry-run
    python -m scripts.delete_from_chroma --page-title "Terraria Boss Progression Roadmap" --collection terraria_wiki --force
    python -m scripts.delete_from_chroma --page-title "Terraria Boss Progression Roadmap" --collection terraria_walkthrough_walkthrough_links --source-partition custom --force
"""

from __future__ import annotations

import argparse
from typing import Any

import chromadb

from config import CHROMADB_PATH, CHROMADB_COLLECTION


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete Chroma chunks by page_title.")
    parser.add_argument(
        "--page-title",
        required=True,
        help="Exact page_title metadata to match.",
    )
    parser.add_argument(
        "--collection",
        action="append",
        default=None,
        help=(
            "Collection name to target. Can be provided multiple times. "
            "If omitted, defaults to CHROMADB_COLLECTION unless --all-collections is used."
        ),
    )
    parser.add_argument(
        "--all-collections",
        action="store_true",
        help="Target all collections found in CHROMADB_PATH.",
    )
    parser.add_argument(
        "--source-partition",
        default=None,
        help="Optional filter for source_partition (e.g. custom, core, walkthrough_links).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview matching records without deleting.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Execute deletion without interactive confirmation.",
    )
    return parser


def _build_where(page_title: str, source_partition: str | None) -> dict[str, Any]:
    if source_partition and source_partition.strip():
        return {
            "$and": [
                {"page_title": page_title},
                {"source_partition": source_partition.strip()},
            ]
        }
    return {"page_title": page_title}


def _target_collections(client: chromadb.PersistentClient, args: argparse.Namespace) -> list[str]:
    existing_names = [c.name for c in client.list_collections()]

    if args.all_collections:
        return existing_names

    if args.collection:
        return args.collection

    return [CHROMADB_COLLECTION]


def _confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> None:
    args = _build_parser().parse_args()

    client = chromadb.PersistentClient(path=CHROMADB_PATH)
    where = _build_where(args.page_title, args.source_partition)
    target_names = _target_collections(client, args)
    existing_names = {c.name for c in client.list_collections()}

    if not target_names:
        print("No collections found to target.")
        return

    total_matches = 0
    total_deleted = 0

    print(f"Chroma path: {CHROMADB_PATH}")
    print(f"page_title filter: {args.page_title}")
    if args.source_partition:
        print(f"source_partition filter: {args.source_partition}")
    print(f"Dry run: {args.dry_run}")

    plans: list[tuple[str, int, int]] = []

    for name in target_names:
        if name not in existing_names:
            print(f"[skip] Collection not found: {name}")
            continue

        collection = client.get_collection(name)
        before = collection.count()

        preview = collection.get(where=where, include=["metadatas"], limit=10000)
        matched_ids = preview.get("ids", [])
        matched = len(matched_ids)
        total_matches += matched

        plans.append((name, before, matched))

    if not plans:
        print("No valid collections selected.")
        return

    print("\nPlanned actions:")
    for name, before, matched in plans:
        print(f"- {name}: matched={matched}, collection_count_before={before}")

    if args.dry_run:
        print("\nDry run only. No data deleted.")
        return

    if total_matches == 0:
        print("\nNo matching chunks found. Nothing deleted.")
        return

    if not args.force:
        if not _confirm("Proceed with deletion?"):
            print("Cancelled.")
            return

    for name, before, matched in plans:
        if matched == 0:
            continue

        collection = client.get_collection(name)
        collection.delete(where=where)
        after = collection.count()
        deleted = max(before - after, 0)
        total_deleted += deleted
        print(f"[done] {name}: before={before}, after={after}, removed={deleted}")

    print(f"\nFinished. Total matched={total_matches}, total removed={total_deleted}.")


if __name__ == "__main__":
    main()

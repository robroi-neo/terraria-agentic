"""
Index a custom Markdown document into ChromaDB using the existing ingestion pipeline.

Usage examples:
    python -m scripts.index_custom_markdown --file ./docs/boss_roadmap.md --categories Bosses Progression
    python -m scripts.index_custom_markdown --markdown "# Boss List: Roadmap\nthese are the boss progression in terraria\n- Eye of Cthulhu" --categories Bosses
    python -m scripts.index_custom_markdown --file ./docs/boss_roadmap.md --title "Boss List: Roadmap" --collection terraria_custom
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.ingestion.chunker import chunk_articles
from src.ingestion.embedder import BGEEmbedder, embed_and_index
from src.ingestion.indexer import ChromaIndexer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index one custom Markdown document.")
    parser.add_argument(
        "--file",
        default=None,
        help="Path to a markdown file (.md).",
    )
    parser.add_argument(
        "--markdown",
        default=None,
        help="Inline markdown content. Use this instead of --file when needed.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional explicit title. If omitted, title is inferred from first markdown heading or first line.",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="Optional category labels. Stored in the existing 'category' metadata tag.",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Optional ChromaDB collection override.",
    )
    parser.add_argument(
        "--chroma-path",
        default=None,
        help="Optional ChromaDB persist directory override.",
    )
    parser.add_argument(
        "--source-url",
        default=None,
        help="Optional source URL metadata. Defaults to file path or custom://<slug>.",
    )
    return parser


def _read_markdown(file_path: str | None, inline_markdown: str | None) -> str:
    if bool(file_path) == bool(inline_markdown):
        raise ValueError("Provide exactly one of --file or --markdown.")

    if inline_markdown is not None:
        text = inline_markdown.strip()
        if not text:
            raise ValueError("--markdown cannot be empty.")
        return text

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Markdown file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Markdown file is empty: {path}")
    return text


def _infer_title(markdown_text: str, explicit_title: str | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()

    lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    if not lines:
        return "Custom Markdown Document"

    first = lines[0]
    if first.startswith("#"):
        inferred = first.lstrip("#").strip()
        return inferred or "Custom Markdown Document"
    return first


def _extract_sections(markdown_text: str) -> List[Dict[str, str]]:
    lines = markdown_text.splitlines()
    sections: List[Dict[str, str]] = []

    current_title = "Document"
    current_path = "Document"
    buffer: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if buffer:
                text = "\n".join(buffer).strip()
                if text:
                    sections.append({"title": current_title, "path": current_path, "text": text})
            header = stripped.lstrip("#").strip() or "Untitled"
            current_title = header
            current_path = header
            buffer = []
            continue
        buffer.append(line)

    if buffer:
        text = "\n".join(buffer).strip()
        if text:
            sections.append({"title": current_title, "path": current_path, "text": text})

    if not sections:
        plain = markdown_text.strip()
        if plain:
            sections.append({"title": "Document", "path": "Document", "text": plain})

    return sections


def _build_article(
    markdown_text: str,
    title: str,
    categories: List[str],
    source_url: str,
) -> Dict[str, Any]:
    categories_clean = [c.strip() for c in categories if c and c.strip()]
    category_tag = " | ".join(categories_clean) if categories_clean else "custom"
    pageid_seed = f"{title}|{source_url}|{category_tag}"
    pageid = int(hashlib.sha1(pageid_seed.encode("utf-8")).hexdigest()[:12], 16)

    return {
        "title": title,
        "pageid": pageid,
        "source_url": source_url,
        "category": category_tag,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "cleaned_text": markdown_text,
        "sections": _extract_sections(markdown_text),
        "source_partition": "custom",
    }


async def main() -> None:
    args = _build_parser().parse_args()

    markdown_text = _read_markdown(args.file, args.markdown)
    title = _infer_title(markdown_text, args.title)
    categories = args.categories or []

    if args.source_url:
        source_url = args.source_url
    elif args.file:
        source_url = str(Path(args.file).resolve())
    else:
        slug = "-".join(title.lower().split()) or "custom-markdown"
        source_url = f"custom://{slug}"

    article = _build_article(
        markdown_text=markdown_text,
        title=title,
        categories=categories,
        source_url=source_url,
    )

    chunk_list = chunk_articles([article])
    if not chunk_list:
        raise RuntimeError("No chunks generated from markdown. Document may be empty.")

    indexer_kwargs: Dict[str, Any] = {}
    if args.collection:
        indexer_kwargs["collection_name"] = args.collection
    if args.chroma_path:
        indexer_kwargs["persist_directory"] = args.chroma_path

    embedder = BGEEmbedder()
    indexer = ChromaIndexer(**indexer_kwargs)
    await embed_and_index(chunk_list, embedder, indexer)

    total = await indexer.count()
    category_tag = article.get("category", "custom")
    print(f"Indexed custom markdown: '{title}'")
    print(f"Category tag: {category_tag}")
    print(f"Chunks indexed: {len(chunk_list)}")
    print(f"Collection count now: {total}")


if __name__ == "__main__":
    asyncio.run(main())

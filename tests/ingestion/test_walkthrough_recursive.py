import os

# Ensure config safety checks pass for local smoke runs.
os.environ.setdefault("EMBEDDER_MODEL", "BAAI/bge-base-en-v1.5")

from src.ingestion.scraper import (  # noqa: E402
    extract_infobox_and_sections,
    _extract_clickable_titles,
    _is_crawlable_title,
)
from src.ingestion.chunker import chunk_article  # noqa: E402


def run_extract_hierarchy_test() -> None:
    html = """
    <div class=\"mw-parser-output\">
      <h2><span class=\"mw-headline\">Starting Out</span></h2>
      <p>Begin with simple gear.</p>
      <h3><span class=\"mw-headline\">Beginning</span></h3>
      <p>Gather wood and build shelter.</p>
      <h3><span class=\"mw-headline\">Night</span></h3>
      <p>Survive zombies and demon eyes.</p>
    </div>
    """

    parsed = extract_infobox_and_sections(html)
    sections = parsed["sections"]
    assert len(sections) == 3
    assert sections[0]["path"] == "Starting Out"
    assert sections[1]["path"] == "Starting Out > Beginning"
    assert sections[2]["path"] == "Starting Out > Night"
    print("run_extract_hierarchy_test PASSED")


def run_extract_clickable_titles_test() -> None:
    section_html = """
    <p>
      Use <a href=\"/wiki/Copper_Pickaxe\">Copper Pickaxe</a> first.
      Then craft <a href=\"https://terraria.wiki.gg/wiki/Eye_of_Cthulhu\">Eye of Cthulhu prep</a>.
      Ignore <a href=\"https://example.com/other\">external</a> links.
    </p>
    """

    titles = _extract_clickable_titles(section_html)
    assert "Copper Pickaxe" in titles
    assert "Eye of Cthulhu" in titles
    assert all("example.com" not in title for title in titles)
    print("run_extract_clickable_titles_test PASSED")


def run_crawl_filter_test() -> None:
    blocked_namespaces = ["file", "template", "talk", "category", "special", "user", "legacy"]

    assert _is_crawlable_title("Copper Pickaxe", include_guide_links=False, excluded_namespaces=blocked_namespaces)
    assert not _is_crawlable_title("File:Guide.png", include_guide_links=False, excluded_namespaces=blocked_namespaces)
    assert not _is_crawlable_title("Guide:Class setups", include_guide_links=False, excluded_namespaces=blocked_namespaces)
    assert _is_crawlable_title("Guide:Class setups", include_guide_links=True, excluded_namespaces=blocked_namespaces)
    print("run_crawl_filter_test PASSED")


def run_chunk_metadata_test() -> None:
    article = {
        "title": "Guide:Walkthrough",
        "pageid": 123,
        "source_url": "https://terraria.wiki.gg/wiki/Guide:Walkthrough",
        "category": "specific",
        "last_updated": "2026-03-01T00:00:00Z",
        "is_root_walkthrough": True,
        "source_partition": "walkthrough_root",
        "discovered_from": "Guide:Walkthrough",
        "crawl_depth": 0,
        "root_page_title": "Guide:Walkthrough",
        "sections": [
            {
                "title": "Starting Out",
                "path": "Starting Out > Beginning",
                "text": "Get wood, build shelter, craft tools, and explore caves for life crystals.",
            }
        ],
    }

    chunks = chunk_article(article)
    assert len(chunks) > 0
    first = chunks[0]
    assert first["source_partition"] == "walkthrough_root"
    assert first["is_root_walkthrough"] is True
    assert first["section_path"] == "Starting Out > Beginning"
    assert first["crawl_depth"] == 0
    print("run_chunk_metadata_test PASSED")


if __name__ == "__main__":
    run_extract_hierarchy_test()
    run_extract_clickable_titles_test()
    run_crawl_filter_test()
    run_chunk_metadata_test()
    print("test_walkthrough_recursive PASSED")

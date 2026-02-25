"""
Cleaner for MediaWiki text extracts.
Removes MediaWiki markup, templates, file/image links, references, and formatting markup.
Converts internal links to readable text.
"""
import re
from typing import List

def clean_mediawiki_text(text: str) -> str:
    # Remove templates: {{...}}
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # Remove nested templates (simple, not perfect)
    while re.search(r"\{\{[^{}]*\}\}", text):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # Remove file/image links: [[File:...]] or [[Image:...]]
    text = re.sub(r"\[\[(File|Image):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    # Remove references: <ref>...</ref> and <ref .../>
    text = re.sub(r"<ref[^>/]*?/>", "", text)
    text = re.sub(r"<ref[^>]*?>.*?</ref>", "", text, flags=re.DOTALL)
    # Remove formatting markup: '''bold''', ''italic''
    text = re.sub(r"'''+", "", text)
    text = re.sub(r"''+", "", text)
    # Convert internal links [[Page|Text]] or [[Page]] to 'Text' or 'Page'
    def repl_link(match):
        parts = match.group(1).split("|")
        return parts[-1].strip()
    text = re.sub(r"\[\[([^\]]+)\]\]", repl_link, text)
    # Remove external links [http://... label] or [http://...]
    text = re.sub(r"\[https?://[^\s\]]+( [^\]]+)?\]", lambda m: m.group(1).strip() if m.group(1) else "", text)
    # Remove HTML comments <!-- ... -->
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Remove any remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove any remaining curly braces (rare)
    text = re.sub(r"[{}]", "", text)
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()

if __name__ == "__main__":
    sample = """
    '''Bold''' and ''italic'' text. [[Page|Display Text]] and [[Page]].
    {{Infobox|data}} [[File:Example.png]] <ref>Reference</ref>
    [https://example.com Label] [https://example.com]
    <!-- Comment -->
    """
    print(clean_mediawiki_text(sample))

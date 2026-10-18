"""Convert HN's HTML-ish text fields to plain text."""
import html
import re

_PARAGRAPH = re.compile(r"<p>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = _PARAGRAPH.sub("\n\n", raw)
    text = _TAG.sub("", text)
    # Unescape after stripping tags, so "&lt;b&gt;" written by a user stays as text.
    text = html.unescape(text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()

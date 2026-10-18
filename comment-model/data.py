"""Turn the HN post -> comment pairs into chat examples for fine-tuning."""
import json
import re
from pathlib import Path

PAIRS_DIR = Path(__file__).parent.parent / "hn-comments-dataset" / "data"

SYSTEM_PROMPT = (
    "You comment on professional social media posts (LinkedIn style). "
    "Write one short, relevant comment that reacts to the substance of the post: "
    "a concrete question, a related experience, or a reasoned opinion. "
    "No hashtags, no emojis, no generic praise. Reply in the language of the post."
)

MAX_POST_CHARS = 1500
_URL = re.compile(r"https?://")
_NOISE = ("[flagged]", "[dead]", "[deleted]")


def keep_comment(text: str, min_chars: int = 40, max_chars: int = 600) -> bool:
    """Drop comments that make poor LinkedIn-style targets."""
    if not (min_chars <= len(text) <= max_chars):
        return False
    if text.lstrip().startswith(">"):  # mostly quoting someone else
        return False
    if len(_URL.findall(text)) > 1:  # link dumps
        return False
    return not any(n in text for n in _NOISE)


def messages(post: str) -> list[dict]:
    post = post.strip()
    if len(post) > MAX_POST_CHARS:
        post = post[:MAX_POST_CHARS].rsplit(" ", 1)[0] + " …"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Post:\n{post}"},
    ]


def load_pairs(split: str, limit: int | None = None) -> list[dict]:
    rows = []
    with (PAIRS_DIR / f"pairs_{split}.jsonl").open(encoding="utf8") as f:
        for line in f:
            row = json.loads(line)
            if keep_comment(row["comment"]):
                rows.append({"post": row["post"], "comment": row["comment"].strip()})
                if limit and len(rows) >= limit:
                    break
    return rows

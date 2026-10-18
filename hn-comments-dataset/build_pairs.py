"""Join scraped stories and comments into post -> comment pairs for fine-tuning.

    python build_pairs.py --max-per-post 3 --max-chars 600 --val-ratio 0.05

Writes data/pairs_train.jsonl and data/pairs_val.jsonl. The split is done by story,
so all comments of a post land on the same side (no leakage into validation).
"""
import argparse
import json
import zlib
from pathlib import Path

DATA = Path(__file__).parent / "data"


def read_jsonl(path: Path) -> dict[int, dict]:
    """Rows keyed by id; the last occurrence wins (feeds are appended across runs)."""
    rows = {}
    if path.exists():
        with path.open(encoding="utf8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    rows[row["id"]] = row
    return rows


def post_text(story: dict) -> str:
    return f"{story['title']}\n\n{story['text']}".strip() if story["text"] else story["title"]


def build_pairs(stories: dict[int, dict], comments: dict[int, dict], *, max_per_post: int,
                min_chars: int, max_chars: int) -> list[dict]:
    by_story: dict[int, list[dict]] = {}
    for c in comments.values():
        if c["depth"] == 1 and c["story_id"] in stories and min_chars <= len(c["text"]) <= max_chars:
            by_story.setdefault(c["story_id"], []).append(c)

    pairs = []
    for story_id, story_comments in sorted(by_story.items()):
        story = stories[story_id]
        for c in sorted(story_comments, key=lambda c: c["rank"])[:max_per_post]:
            pairs.append({
                "story_id": story_id,
                "comment_id": c["id"],
                "post": post_text(story),
                "comment": c["text"],
                "rank": c["rank"],
            })
    return pairs


def is_val(story_id: int, ratio: float) -> bool:
    # Stable across runs and machines (unlike hash()).
    return zlib.crc32(str(story_id).encode()) % 10_000 < ratio * 10_000


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-per-post", type=int, default=3, help="best-ranked comments kept per post")
    p.add_argument("--min-chars", type=int, default=20)
    p.add_argument("--max-chars", type=int, default=600, help="LinkedIn-style comments are short")
    p.add_argument("--val-ratio", type=float, default=0.05)
    args = p.parse_args()

    stories = read_jsonl(DATA / "stories.jsonl")
    comments = read_jsonl(DATA / "comments.jsonl")
    pairs = build_pairs(stories, comments, max_per_post=args.max_per_post,
                        min_chars=args.min_chars, max_chars=args.max_chars)
    train = [r for r in pairs if not is_val(r["story_id"], args.val_ratio)]
    val = [r for r in pairs if is_val(r["story_id"], args.val_ratio)]
    write_jsonl(DATA / "pairs_train.jsonl", train)
    write_jsonl(DATA / "pairs_val.jsonl", val)

    posts = len({r["story_id"] for r in pairs})
    print(f"{len(stories)} stories, {len(comments)} comments -> {len(pairs)} pairs from {posts} posts")
    print(f"train: {len(train)}  val: {len(val)}  ({DATA})")


if __name__ == "__main__":
    main()

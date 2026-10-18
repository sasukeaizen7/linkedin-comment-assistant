from build_pairs import build_pairs, is_val, post_text
from hnspider.text import html_to_text


def test_html_to_text_paragraphs_links_and_entities():
    raw = 'First line &amp; more.<p>See <a href="https://x.io">https://x.io</a> &#x2F; <i>now</i>'
    assert html_to_text(raw) == "First line & more.\n\nSee https://x.io / now"


def test_html_to_text_keeps_escaped_tags_as_text():
    assert html_to_text("use &lt;b&gt; for bold") == "use <b> for bold"


def test_html_to_text_empty():
    assert html_to_text(None) == ""


def story(id, title="T", text=""):
    return {"id": id, "title": title, "text": text}


def comment(id, story_id, rank, text="a" * 30, depth=1):
    return {"id": id, "story_id": story_id, "rank": rank, "text": text, "depth": depth}


def test_post_text_joins_title_and_body():
    assert post_text(story(1, "Ask HN: x?", "body")) == "Ask HN: x?\n\nbody"
    assert post_text(story(1, "Link title")) == "Link title"


def test_build_pairs_filters_and_orders():
    stories = {1: story(1), 2: story(2)}
    comments = {
        10: comment(10, 1, rank=2),
        11: comment(11, 1, rank=0),
        12: comment(12, 1, rank=1),
        13: comment(13, 1, rank=3, depth=2),  # reply to a comment: not a pair
        14: comment(14, 1, rank=4, text="short"),  # too short
        15: comment(15, 99, rank=0),  # story not scraped
        16: comment(16, 2, rank=0, text="b" * 700),  # too long
    }
    pairs = build_pairs(stories, comments, max_per_post=2, min_chars=20, max_chars=600)
    assert [p["comment_id"] for p in pairs] == [11, 12]


def test_split_is_stable_and_roughly_proportional():
    val = [i for i in range(10_000) if is_val(i, 0.05)]
    assert val == [i for i in range(10_000) if is_val(i, 0.05)]
    assert 350 < len(val) < 650

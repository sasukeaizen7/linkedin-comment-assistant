"""Hacker News stories and their comment trees, via the official Firebase API.

    scrapy crawl hn -a lists=best,ask,show -a limit=200 -a max_comments=10 -a max_depth=1
"""
import scrapy

from hnspider.items import CommentItem, StoryItem

API = "https://hacker-news.firebaseio.com/v0"
LISTS = {
    "top": "topstories",
    "best": "beststories",
    "new": "newstories",
    "ask": "askstories",
    "show": "showstories",
}


def item_url(item_id: int) -> str:
    return f"{API}/item/{item_id}.json"


def is_alive(item: dict | None, kind: str) -> bool:
    return bool(item) and item.get("type") == kind and not item.get("deleted") and not item.get("dead")


class HackerNewsSpider(scrapy.Spider):
    name = "hn"
    allowed_domains = ["hacker-news.firebaseio.com"]

    def __init__(self, lists="best,ask,show", limit=100, max_comments=10, max_depth=1, min_comments=3, **kwargs):
        super().__init__(**kwargs)
        self.lists = [name.strip() for name in lists.split(",") if name.strip()]
        unknown = set(self.lists) - LISTS.keys()
        if unknown:
            raise ValueError(f"unknown list(s) {sorted(unknown)}; choose from {sorted(LISTS)}")
        self.limit = int(limit)  # stories per list (the API returns up to 500)
        self.max_comments = int(max_comments)  # children followed per item
        self.max_depth = int(max_depth)  # 1 = only direct replies to the story
        self.min_comments = int(min_comments)  # skip stories with fewer comments

    async def start(self):
        for name in self.lists:
            yield scrapy.Request(f"{API}/{LISTS[name]}.json", callback=self.parse_list, cb_kwargs={"source": name})

    def parse_list(self, response, source):
        for story_id in response.json()[: self.limit]:
            yield scrapy.Request(item_url(story_id), callback=self.parse_story, cb_kwargs={"source": source})

    def parse_story(self, response, source):
        story = response.json()
        if not is_alive(story, "story") or story.get("descendants", 0) < self.min_comments:
            return
        yield StoryItem(
            id=story["id"],
            title=story.get("title", ""),
            text=story.get("text", ""),
            url=story.get("url"),
            score=story.get("score", 0),
            num_comments=story.get("descendants", 0),
            time=story["time"],
            source_list=source,
        )
        yield from self.follow_kids(story, story_id=story["id"], depth=1)

    def parse_comment(self, response, story_id, depth, rank):
        comment = response.json()
        if not is_alive(comment, "comment") or not comment.get("text"):
            return
        yield CommentItem(
            id=comment["id"],
            story_id=story_id,
            parent_id=comment["parent"],
            depth=depth,
            rank=rank,
            text=comment["text"],
            time=comment["time"],
        )
        if depth < self.max_depth:
            yield from self.follow_kids(comment, story_id=story_id, depth=depth + 1)

    def follow_kids(self, parent, story_id, depth):
        # "kids" is already in HN's ranking order, so the first ones are the best.
        for rank, kid in enumerate(parent.get("kids", [])[: self.max_comments]):
            yield scrapy.Request(
                item_url(kid),
                callback=self.parse_comment,
                cb_kwargs={"story_id": story_id, "depth": depth, "rank": rank},
            )

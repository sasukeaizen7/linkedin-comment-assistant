"""Older Hacker News stories, found through the Algolia HN Search API.

    scrapy crawl hn_history -a tags=ask_hn,show_hn,story -a max_stories=3000 -a min_comments=20

For each story found on Algolia, two requests:
  1. the official API item -> story fields and "kids" in HN's ranking order;
  2. the Algolia item       -> the whole comment tree in one response.
Comment texts come from (2), their rank from (1), so the best comments come first
(Algolia sorts children by id, not by rank).
"""
import scrapy

from hnspider.items import CommentItem, StoryItem
from hnspider.spiders.hn import is_alive, item_url

ALGOLIA = "https://hn.algolia.com/api/v1"
TAGS = {"ask_hn", "show_hn", "story"}
PAGE_SIZE = 1000  # Algolia's maximum hitsPerPage


class HackerNewsHistorySpider(scrapy.Spider):
    name = "hn_history"
    allowed_domains = ["hn.algolia.com", "hacker-news.firebaseio.com"]
    custom_settings = {
        # Algolia allows 10,000 requests/hour per IP: stay well under it.
        "DOWNLOAD_DELAY": 0.45,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": False,
        # Full comment trees can weigh hundreds of KB each: don't cache them.
        "HTTPCACHE_ENABLED": False,
    }

    def __init__(self, tags="ask_hn,show_hn,story", max_stories=1000, min_comments=20, min_points=10,
                 max_comments=10, before=None, **kwargs):
        super().__init__(**kwargs)
        self.tags = [t.strip() for t in tags.split(",") if t.strip()]
        unknown = set(self.tags) - TAGS
        if unknown:
            raise ValueError(f"unknown tag(s) {sorted(unknown)}; choose from {sorted(TAGS)}")
        self.max_stories = int(max_stories)  # per tag
        self.min_comments = int(min_comments)
        self.min_points = int(min_points)
        self.max_comments = int(max_comments)  # best-ranked direct replies kept per story
        self.before = int(before) if before else None  # unix time: only stories older than this
        self.found = dict.fromkeys(self.tags, 0)

    async def start(self):
        for tag in self.tags:
            yield self.search(tag, self.before)

    def search(self, tag, before):
        # search_by_date is newest first; walking a created_at_i cursor avoids
        # Algolia's 1,000-hit limit on page-based pagination.
        filters = f"num_comments>={self.min_comments},points>={self.min_points}"
        if before:
            filters += f",created_at_i<{before}"
        url = (f"{ALGOLIA}/search_by_date?tags={tag}&numericFilters={filters}&hitsPerPage={PAGE_SIZE}"
               "&attributesToRetrieve=objectID,created_at_i&attributesToHighlight=")
        return scrapy.Request(url, callback=self.parse_search, cb_kwargs={"tag": tag}, dont_filter=True)

    def parse_search(self, response, tag):
        hits = response.json()["hits"]
        for hit in hits:
            if self.found[tag] >= self.max_stories:
                return
            self.found[tag] += 1
            yield scrapy.Request(item_url(int(hit["objectID"])), callback=self.parse_story,
                                 cb_kwargs={"tag": tag})
        if len(hits) == PAGE_SIZE:
            yield self.search(tag, min(h["created_at_i"] for h in hits))
        self.logger.info("%s: %d stories queued", tag, self.found[tag])

    def parse_story(self, response, tag):
        story = response.json()
        if not is_alive(story, "story"):
            return
        ranks = {kid: rank for rank, kid in enumerate(story.get("kids", [])[: self.max_comments])}
        if not ranks:
            return
        yield StoryItem(
            id=story["id"],
            title=story.get("title", ""),
            text=story.get("text", ""),
            url=story.get("url"),
            score=story.get("score", 0),
            num_comments=story.get("descendants", 0),
            time=story["time"],
            source_list=tag,
        )
        yield scrapy.Request(f"{ALGOLIA}/items/{story['id']}", callback=self.parse_tree,
                             cb_kwargs={"story_id": story["id"], "ranks": ranks})

    def parse_tree(self, response, story_id, ranks):
        for child in response.json().get("children", []):
            if child["id"] in ranks and child.get("text"):
                yield CommentItem(
                    id=child["id"],
                    story_id=story_id,
                    parent_id=story_id,
                    depth=1,
                    rank=ranks[child["id"]],
                    text=child["text"],
                    time=child["created_at_i"],
                )

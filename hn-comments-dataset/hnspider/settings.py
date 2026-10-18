BOT_NAME = "hnspider"
SPIDER_MODULES = ["hnspider.spiders"]
NEWSPIDER_MODULE = "hnspider.spiders"

# Identify the bot honestly and follow the API's robots.txt (it allows *.json).
USER_AGENT = "hnspider/1.0 (personal research dataset; Scrapy)"
ROBOTSTXT_OBEY = True

# Be polite: the Firebase API is fast, but there is no reason to hammer it.
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0
RETRY_TIMES = 3

# Re-runs while developing hit the local cache instead of the API.
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 6 * 3600
HTTPCACHE_DIR = "httpcache"

ITEM_PIPELINES = {
    "hnspider.pipelines.CleanTextPipeline": 100,
}
MIN_COMMENT_CHARS = 20

# Append so several runs accumulate; build_pairs.py de-duplicates by id.
FEEDS = {
    "data/stories.jsonl": {
        "format": "jsonlines",
        "encoding": "utf8",
        "item_classes": ["hnspider.items.StoryItem"],
        "overwrite": False,
    },
    "data/comments.jsonl": {
        "format": "jsonlines",
        "encoding": "utf8",
        "item_classes": ["hnspider.items.CommentItem"],
        "overwrite": False,
    },
}

LOG_LEVEL = "INFO"

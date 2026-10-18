from scrapy.exceptions import DropItem

from hnspider.items import CommentItem, StoryItem
from hnspider.text import html_to_text


class CleanTextPipeline:
    def __init__(self, min_comment_chars: int):
        self.min_comment_chars = min_comment_chars

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getint("MIN_COMMENT_CHARS", 20))

    def process_item(self, item):
        if isinstance(item, StoryItem):
            item.title = html_to_text(item.title)
            item.text = html_to_text(item.text)
        elif isinstance(item, CommentItem):
            item.text = html_to_text(item.text)
            if len(item.text) < self.min_comment_chars:
                raise DropItem(f"comment {item.id} too short")
        return item

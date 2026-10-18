from dataclasses import dataclass


# Usernames are deliberately not stored: the dataset only needs the text.
@dataclass
class StoryItem:
    id: int
    title: str
    text: str
    url: str | None
    score: int
    num_comments: int
    time: int
    source_list: str


@dataclass
class CommentItem:
    id: int
    story_id: int
    parent_id: int
    depth: int  # 1 = direct reply to the story
    rank: int  # position among siblings, in HN's ranking order (0 = best)
    text: str
    time: int

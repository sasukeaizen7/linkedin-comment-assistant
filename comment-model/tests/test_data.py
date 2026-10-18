from data import MAX_POST_CHARS, keep_comment, messages


def test_keep_comment_filters():
    good = "We hit the same issue with Kafka consumer lag; partition count was the fix."
    assert keep_comment(good)
    assert not keep_comment("Too short.")
    assert not keep_comment("x" * 601)
    assert not keep_comment("> quoting the post\nand then a reply that is long enough")
    assert not keep_comment("see https://a.io and https://b.io for more details on this")
    assert not keep_comment("[flagged] something something something something")


def test_messages_truncates_long_posts():
    msgs = messages("word " * 1000)
    assert msgs[0]["role"] == "system"
    assert len(msgs[1]["content"]) <= len("Post:\n") + MAX_POST_CHARS + 2
    assert msgs[1]["content"].endswith("…")

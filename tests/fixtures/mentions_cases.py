from tests.fixtures.tokenizer_cases import TokenizerCase

MENTIONS_CASES = (
    TokenizerCase(
        name="simple mention",
        text="@user hello",
        expected_hashtags=(),
        expected_mentions=("@user",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="mention with dotted username is not email",
        text="@john.doe hello",
        expected_hashtags=(),
        expected_mentions=("@john.doe",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="mention followed by sentence period is not swallowed",
        text="thanks @john. bye",
        expected_hashtags=(),
        expected_mentions=("@john",),
        expected_words=("thanks", "bye"),
        expected_tokens="bye\x1fthanks",
    ),

    TokenizerCase(
        name="mention with consecutive periods stops early",
        text="@maya..studio hello",
        expected_hashtags=(),
        expected_mentions=("@maya",),
        expected_words=("studio", "hello"),
        expected_tokens="hello\x1fstudio",
    ),

    TokenizerCase(
        name="mention followed immediately by word",
        text="@userHello",
        expected_hashtags=(),
        expected_mentions=("@userHello",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="mention terminated by emoji",
        text="@hello😀world",
        expected_hashtags=(),
        expected_mentions=("@hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="unicode mention",
        text="@нейтан hello",
        expected_hashtags=(),
        expected_mentions=("@нейтан",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="multiple mentions",
        text="@alice and @bob talk",
        expected_hashtags=(),
        expected_mentions=("@alice", "@bob"),
        expected_words=("and", "talk"),
        expected_tokens="and\x1ftalk",
    ),

    TokenizerCase(
        name="mention with unicode digits",
        text="@user123 hello",
        expected_hashtags=(),
        expected_mentions=("@user123",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="mention followed by punctuation",
        text="thanks @john, bye",
        expected_hashtags=(),
        expected_mentions=("@john",),
        expected_words=("thanks", "bye"),
        expected_tokens="bye\x1fthanks",
    ),

    TokenizerCase(
        name="mention followed by second mention",
        text="@alice@bob hello",
        expected_hashtags=(),
        expected_mentions=("@alice", "@bob"),
        expected_words=("hello",),
        expected_tokens="hello",
    ),
)
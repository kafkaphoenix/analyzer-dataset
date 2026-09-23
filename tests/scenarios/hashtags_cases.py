from tests.scenarios.tokenizer_cases import TokenizerCase

HASHTAGS_CASES = (
    TokenizerCase(
        name="ascii punctuation inside hashtag",
        text="#hello!world",
        expected_hashtags=("#hello!world",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="hashtag followed by whitespace",
        text="#hello world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="emoji inside hashtag followed by whitespace",
        text="#hello😀 world",
        expected_hashtags=("#hello😀",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="emoji inside hashtag followed by letters",
        text="#hello😀world",
        expected_hashtags=("#hello😀world",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="heart symbol inside hashtag",
        text="#hello❤world",
        expected_hashtags=("#hello❤world",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="copyright symbol inside hashtag",
        text="#hello©world",
        expected_hashtags=("#hello©world",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="egyptian symbol inside hashtag",
        text="#maharastra𓽤khudko",
        expected_hashtags=("#maharastra𓽤khudko",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="arabic comma inside hashtag",
        text="#،like",
        expected_hashtags=("#،like",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="double hashtag with whitespace",
        text="#holathis #this",
        expected_hashtags=("#holathis", "#this"),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="double hashtag without whitespace",
        text="#hola#hola",
        expected_hashtags=("#hola", "#hola"),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="hashtag followed by no-break space",
        text="#for\u00a0you",
        expected_words=("you",),
        expected_mentions=(),
        expected_hashtags=("#for",),
        expected_emails=(),
        expected_tokens="you",
    ),

    TokenizerCase(
        name="hashtag glued to bare domain requiring path",
        text="#dealbit.ly/promo hello",
        expected_hashtags=("#deal",),
        expected_mentions=(),
        expected_urls=("bit.ly/promo",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="hashtag followed by mention",
        text="#alice@hello",
        expected_hashtags=("#alice",),
        expected_mentions=("@hello",),
        expected_words=(),
        expected_tokens="",
    ),
)

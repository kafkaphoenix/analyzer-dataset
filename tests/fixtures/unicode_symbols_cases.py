from tests.fixtures.tokenizer_cases import TokenizerCase

UNICODE_SYMBOLS_CASES = (
    TokenizerCase(
        name="egyptian symbol terminates hashtag",
        text="#maharastra𓽤khudko",
        expected_hashtags=("#maharastra",),
        expected_words=("khudko",),
        expected_tokens="khudko",
    ),

    TokenizerCase(
        name="egyptian symbol between words",
        text="hello𓽤world",
        expected_hashtags=(),
        expected_words=("hello", "world"),
        expected_tokens="hello\x1fworld",
    ),

    TokenizerCase(
        name="symbol terminates hashtag",
        text="#hello©world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="emoji terminates hashtag",
        text="#hello😀world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="heart terminates hashtag",
        text="#hello❤world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="linear b is valid hashtag character",
        text="#L𐀏ckIn hello",
        expected_hashtags=("#L𐀏ckIn",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode letter continues hashtag",
        text="#hello𐀏world",
        expected_hashtags=("#hello𐀏world",),
        expected_words=(),
        expected_tokens="",
    ),
)
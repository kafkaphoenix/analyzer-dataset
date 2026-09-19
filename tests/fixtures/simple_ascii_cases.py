from tests.fixtures.tokenizer_cases import TokenizerCase

SIMPLE_ASCII_CASES = (
    TokenizerCase(
        name="simple hashtag",
        text="#hello world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="hashtag followed immediately by word",
        text="#helloWorld",
        expected_hashtags=("#helloWorld",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="multiple hashtags",
        text="#hello #world test",
        expected_hashtags=("#hello", "#world"),
        expected_words=("test",),
        expected_tokens="test",
    ),

    TokenizerCase(
        name="underscore in hashtag",
        text="#hello_world test",
        expected_hashtags=("#hello_world",),
        expected_words=("test",),
        expected_tokens="test",
    ),

    TokenizerCase(
        name="numbers in hashtag",
        text="#hello123 test",
        expected_hashtags=("#hello123",),
        expected_words=("test",),
        expected_tokens="test",
    ),
)
from tests.fixtures.tokenizer_cases import TokenizerCase


CASE_FOLDING_CASES = (
    TokenizerCase(
        name="ascii uppercase word",
        text="HELLO WORLD",
        expected_hashtags=(),
        expected_words=("hello", "world"),
        expected_tokens="hello\x1fworld",
    ),

    TokenizerCase(
        name="mixed ascii case",
        text="Hello WoRlD",
        expected_hashtags=(),
        expected_words=("hello", "world"),
        expected_tokens="hello\x1fworld",
    ),

    TokenizerCase( # possible improvement
        name="latin uppercase İ is not folded explicitly",
        text="İzmir hello",
        expected_hashtags=(),
        expected_words=("zmir", "hello"),
        expected_tokens="hello\x1fzmir",
    ),

    TokenizerCase( # possible improvement
        name="alphanumeric words are not supported",
        text="h3ll0 hello",
        expected_hashtags=(),
        expected_words=("hello",),
        expected_tokens="hello",
    ),
)
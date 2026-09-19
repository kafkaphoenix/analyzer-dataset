
from tests.fixtures.tokenizer_cases import TokenizerCase

HASHTAGS_CASES = (
    TokenizerCase(
        name="hashtag followed by punctuation",
        text="#hello!world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="hashtag followed by whitespace",
        text="#hello world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="hashtag followed by emoji and whitespace",
        text="#hello😀 world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="hashtag emoji followed by letters is ambiguous",
        text="#hello😀world",
        expected_hashtags=("#hello",),
        expected_words=("world",),
        expected_tokens="world",
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
)
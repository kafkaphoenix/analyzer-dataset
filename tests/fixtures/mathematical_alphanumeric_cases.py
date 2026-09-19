from tests.fixtures.tokenizer_cases import TokenizerCase

MATHEMATICAL_ALPHANUMERIC_CASES = (
    TokenizerCase(
        name="mathematical alphanumeric hashtag",
        text="#𝐇𝐞𝐥𝐥𝐨 world",
        expected_hashtags=("#𝐇𝐞𝐥𝐥𝐨",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="mathematical alphanumeric hashtag with numbers",
        text="#𝐇𝐞𝐥𝐥𝐨123 world",
        expected_hashtags=("#𝐇𝐞𝐥𝐥𝐨123",),
        expected_words=("world",),
        expected_tokens="world",
    ),

    TokenizerCase(
        name="mathematical symbols",
        text="∑𝐚𝐛𝐜 + 𝐱𝐲𝐳",
        expected_hashtags=(),
        expected_words=(),
        expected_tokens="",
    ),
)
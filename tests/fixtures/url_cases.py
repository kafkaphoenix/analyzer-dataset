from tests.fixtures.tokenizer_cases import TokenizerCase


URL_CASES = (
TokenizerCase(
        name="http url",
        text="visit https://example.com hello",
        expected_hashtags=(),
        expected_words=("visit", "hello"),
        expected_tokens="hello\x1fvisit",
    ),

    TokenizerCase(
        name="www url",
        text="www.example.com hello",
        expected_hashtags=(),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="youtube url",
        text="watch youtu.be/example hello",
        expected_hashtags=(),
        expected_words=("watch", "hello"),
        expected_tokens="hello\x1fwatch",
    ),

    TokenizerCase(
        name="bare youtube.com url",
        text="watch youtube.com/watch?v=abc hello",
        expected_hashtags=(),
        expected_words=("watch", "hello"),
        expected_tokens="hello\x1fwatch",
    ),

    TokenizerCase(
        name="bare mobile youtube url",
        text="m.youtube.com/watch?v=abc hello",
        expected_hashtags=(),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="bare youtube.com with no path",
        text="check youtube.com now",
        expected_hashtags=(),
        expected_words=("check", "now"),
        expected_tokens="check\x1fnow",
    ),

    TokenizerCase(
        name="bit.ly shortlink",
        text="link in bio bit.ly/xyz123 hello",
        expected_hashtags=(),
        expected_words=("link", "bio", "hello"),
        expected_tokens="bio\x1fhello\x1flink",
    ),

    TokenizerCase(
        name="t.co shortlink",
        text="share t.co/abc123 now",
        expected_hashtags=(),
        expected_words=("share", "now"),
        expected_tokens="now\x1fshare",
    ),

    TokenizerCase(
        name="bare t.co with no path is not stripped",
        text="great.com is a real word",
        expected_hashtags=(),
        expected_words=("great", "com", "real", "word"),
        expected_tokens="com\x1fgreat\x1freal\x1fword",
    ),

    TokenizerCase(
        name="tinyurl.com shortlink",
        text="full video tinyurl.com/xyz watch",
        expected_hashtags=(),
        expected_words=("full", "video", "watch"),
        expected_tokens="full\x1fvideo\x1fwatch",
    ),

    TokenizerCase(
        name="goo.gl shortlink",
        text="shortlink goo.gl/abc more info",
        expected_hashtags=(),
        expected_words=("shortlink", "more", "info"),
        expected_tokens="info\x1fmore\x1fshortlink",
    ),

    TokenizerCase(
        name="linktr.ee bio link",
        text="bio link linktr.ee/username here",
        expected_hashtags=(),
        expected_words=("bio", "link", "here"),
        expected_tokens="bio\x1fhere\x1flink",
    ),

    TokenizerCase(
        name="amzn.to affiliate link",
        text="buy here amzn.to/xyz product",
        expected_hashtags=(),
        expected_words=("buy", "here", "product"),
        expected_tokens="buy\x1fhere\x1fproduct",
    ),

    TokenizerCase(
        name="url followed by punctuation",
        text="visit https://example.com, hello",
        expected_hashtags=(),
        expected_words=("visit", "hello"),
        expected_tokens="hello\x1fvisit",
    ),

    TokenizerCase(
        name="url followed by parentheses",
        text="visit https://example.com) hello",
        expected_hashtags=(),
        expected_words=("visit", "hello"),
        expected_tokens="hello\x1fvisit",
    ),

    TokenizerCase(
        name="url followed by unicode whitespace",
        text="visit https://example.com\u00a0hello",
        expected_hashtags=(),
        expected_words=("visit", "hello"),
        expected_tokens="hello\x1fvisit",
    ),

    TokenizerCase(
        name="url followed by exclamation mark",
        text="visit https://example.com! hello",
        expected_hashtags=(),
        expected_words=("visit", "hello"),
        expected_tokens="hello\x1fvisit",
    ),
)
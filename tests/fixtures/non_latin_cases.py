from tests.fixtures.tokenizer_cases import TokenizerCase

NON_LATIN_CASES = (
    TokenizerCase(
        name="unicode devanagari hashtag",
        text="#नमस्ते hello",
        expected_hashtags=("#नमस्ते",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode cyrillic hashtag",
        text="#привет hello",
        expected_hashtags=("#привет",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode thai hashtag",
        text="#สวัสดี hello",
        expected_hashtags=("#สวัสดี",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode japanese hashtag",
        text="#こんにちは hello",
        expected_hashtags=("#こんにちは",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode korean hashtag",
        text="#안녕하세요 hello",
        expected_hashtags=("#안녕하세요",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode arabic hashtag",
        text="#مرحبا hello",
        expected_hashtags=("#مرحبا",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode hebrew hashtag",
        text="#שלום hello",
        expected_hashtags=("#שלום",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode greek hashtag",
        text="#γειά σου hello",
        expected_hashtags=("#γειά",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode armenian hashtag",
        text="#բարեւ hello",
        expected_hashtags=("#բարեւ",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode georgian hashtag",
        text="#გამარჯობა hello",
        expected_hashtags=("#გამარჯობა",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode tamil hashtag",
        text="#வணக்கம் hello",
        expected_hashtags=("#வணக்கம்",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode malayalam hashtag",
        text="#നമസ്കാരം hello",
        expected_hashtags=("#നമസ്കാരം",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode kannada hashtag",
        text="#ನಮಸ್ಕಾರ hello",
        expected_hashtags=("#ನಮಸ್ಕಾರ",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode telugu hashtag",
        text="#నమస్కారం hello",
        expected_hashtags=("#నమస్కారం",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode bengali hashtag",
        text="#হ্যালো hello",
        expected_hashtags=("#হ্যালো",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode urdu hashtag",
        text="#ہیلو hello",
        expected_hashtags=("#ہیلو",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode chinese hashtag",
        text="#你好 hello",
        expected_hashtags=("#你好",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),
)
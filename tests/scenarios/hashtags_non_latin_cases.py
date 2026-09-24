from tests.scenarios.tokenizer_cases import TokenizerCase

HASHTAGS_NON_LATIN_CASES = (
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

    TokenizerCase(
        name="unicode gujarati hashtag",
        text="#નમસ્તે hello",
        expected_hashtags=("#નમસ્તે",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode punjabi hashtag",
        text="#ਸਤ #ਸ੍ਰੀ #ਅਕਾਲ hello",
        expected_hashtags=("#ਸਤ", "#ਸ੍ਰੀ", "#ਅਕਾਲ"),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode odia hashtag",
        text="#ନମସ୍କାର hello",
        expected_hashtags=("#ନମସ୍କାର",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode sinhala hashtag",
        text="#ආයුබෝවන් hello",
        expected_hashtags=("#ආයුබෝවන්",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode khmer hashtag",
        text="#សួស្តី hello",
        expected_hashtags=("#សួស្តី",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode myanmar hashtag",
        text="#မင်္ဂလာပါ hello",
        expected_hashtags=("#မင်္ဂလာပါ",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode cuneiform hashtag",
        text="#𒀀𒁀 hello",
        expected_hashtags=("#𒀀𒁀",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode egyptian hieroglyph hashtag",
        text="#𓀀𓂀 hello",
        expected_hashtags=("#𓀀𓂀",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode mathematical alphanumeric hashtag",
        text="#𝐇𝐞𝐥𝐥𝐨 hello",
        expected_hashtags=("#𝐇𝐞𝐥𝐥𝐨",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode bamum hashtag",
        text="#ꚠꛔ hello",
        expected_hashtags=("#ꚠꛔ",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode linear b hashtag",
        text="#𐀀𐀁 hello",
        expected_hashtags=("#𐀀𐀁",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="unicode combining mark hashtag",
        text="#fypシ゚love hello",
        expected_hashtags=("#fypシ゚love",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="arabic hashtag",
        text="#مرحبا hello",
        expected_hashtags=("#مرحبا",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="arabic punctuation inside hashtag",
        text="#وئرل۔وڈیو______foryou",
        expected_hashtags=("#وئرل۔وڈیو______foryou",),
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
        name="devanagari punctuation inside hashtag",
        text="#।thisbangladesh",
        expected_hashtags=("#।thisbangladesh",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="thai punctuation inside hashtag",
        text="#RBX๛ANSIII",
        expected_hashtags=("#RBX๛ANSIII",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="lao hashtag",
        text="#ຄິດຮອດພໍ່ແມ່ເວລາທໍ້VPN",
        expected_hashtags=("#ຄິດຮອດພໍ່ແມ່ເວລາທໍ້VPN",),
        expected_words=(),
        expected_tokens="",
    ),
)

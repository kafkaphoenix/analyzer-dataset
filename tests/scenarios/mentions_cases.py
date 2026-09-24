from tests.scenarios.tokenizer_cases import TokenizerCase

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
        name="mention consumes trailing sentence period",
        text="thanks @john. bye",
        expected_hashtags=(),
        expected_mentions=("@john.",),
        expected_words=("thanks", "bye"),
        expected_tokens="bye\x1fthanks",
    ),

    TokenizerCase(
        name="mention with consecutive periods is consumed whole",
        text="@maya..studio hello",
        expected_hashtags=(),
        expected_mentions=("@maya..studio",),
        expected_words=("hello",),
        expected_tokens="hello",
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
        name="mention consumes through emoji",
        text="@hello😀world",
        expected_hashtags=(),
        expected_mentions=("@hello😀world",),
        expected_words=(),
        expected_tokens="",
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
        name="old italic unicode mention",
        text="@𐌔han hello",
        expected_hashtags=(),
        expected_mentions=("@𐌔han",),
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
        name="mention consumes trailing punctuation",
        text="thanks @john, bye",
        expected_hashtags=(),
        expected_mentions=("@john,",),
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

    TokenizerCase(
        name="linear a unicode mention",
        text="@𐙚DIXIEིྀ",
        expected_words=(),
        expected_mentions=("@𐙚DIXIEིྀ",),
        expected_hashtags=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="warang citi unicode mention",
        text="@𑣲aaliyah",
        expected_words=(),
        expected_mentions=("@𑣲aaliyah",),
        expected_hashtags=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="unicode mention mongolian supplement",
        text="@ᢉnylah",
        expected_mentions=("@ᢉnylah",),
        expected_hashtags=(),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="unicode mention inscriptional pahlavi",
        text="@𐭩nylah",
        expected_mentions=("@𐭩nylah",),
        expected_hashtags=(),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="unicode mention meroitic hieroglyphs letter, apostrophe absorbed",
        text="@𐦂ave's your was so cute",
        expected_mentions=("@𐦂ave's",),
        expected_hashtags=(),
        expected_words=("your", "was", "cute"),
        expected_tokens="cute\x1fwas\x1fyour",
    ),

    TokenizerCase(
        name="unicode mention carian",
        text="@𐊵nerpa𐊵",
        expected_mentions=("@𐊵nerpa𐊵",),
        expected_hashtags=(),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="unicode mention linear b",
        text="@𐂂magel",
        expected_mentions=("@𐂂magel",),
        expected_hashtags=(),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="unicode mention medefaidrin",
        text="@e𖹭rin",
        expected_mentions=("@e𖹭rin",),
        expected_hashtags=(),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="elbasan unicode mention",
        text="@𐔌han hello",
        expected_hashtags=(),
        expected_mentions=("@𐔌han",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="caucasian albanian unicode mention",
        text="@𐕣han hello",
        expected_hashtags=(),
        expected_mentions=("@𐕣han",),
        expected_words=("hello",),
        expected_tokens="hello",
    ),

    TokenizerCase(
        name="mention with underscore",
        text="Hello @dr.bio_her today",
        expected_hashtags=(),
        expected_mentions=("@dr.bio_her",),
        expected_emails=(),
        expected_words=("hello", "today"),
        expected_tokens="hello\x1ftoday",
    ),

    TokenizerCase(
        name="mention with emoji in middle",
        text="Hello @MRS.Hey🦖BlondeD today",
        expected_hashtags=(),
        expected_mentions=(
            "@MRS.Hey🦖BlondeD",
        ),
        expected_emails=(),
        expected_words=("hello", "today"),
        expected_tokens="hello\x1ftoday",
    ),

    TokenizerCase(
        name="mention with Unicode letter",
        text="Hello @Image.Dummy.Salonextrañando friend",
        expected_hashtags=(),
        expected_mentions=(
            "@Image.Dummy.Salonextrañando",
        ),
        expected_emails=(),
        expected_words=("hello", "friend"),
        expected_tokens="friend\x1fhello",
    ),

    TokenizerCase(
        name="mention with dots digits and underscore",
        text="Hello @7.3_this_E today",
        expected_hashtags=(),
        expected_mentions=(
            "@7.3_this_E",
        ),
        expected_emails=(),
        expected_words=("hello", "today"),
        expected_tokens="hello\x1ftoday",
    ),

    TokenizerCase(
        name="mention ending with underscore",
        text="Hello @mr.big_that today",
        expected_hashtags=(),
        expected_mentions=(
            "@mr.big_that",
        ),
        expected_emails=(),
        expected_words=("hello", "today"),
        expected_tokens="hello\x1ftoday",
    ),

    TokenizerCase(
        name="mention with ellipsis",
        text="Hello @broke.me.to...pieces today",
        expected_hashtags=(),
        expected_mentions=(
            "@broke.me.to...pieces",
        ),
        expected_emails=(),
        expected_words=("hello", "today"),
        expected_tokens="hello\x1ftoday",
    ),

    TokenizerCase(
        name="mention with apostrophe",
        text="Hello @anna'planet moon",
        expected_hashtags=(),
        expected_mentions=(
            "@anna'planet",
        ),
        expected_emails=(),
        expected_words=("hello", "moon"),
        expected_tokens="hello\x1fmoon",
    ),

    TokenizerCase(
        name="mention followed by hashtag",
        text="@alice#hello",
        expected_hashtags=("#hello",),
        expected_mentions=("@alice",),
        expected_words=(),
        expected_tokens="",
    ),

    TokenizerCase(
        name="mention with URL-like domain",
        text="we didn't have pickles @www.dummyhub.com",
        expected_hashtags=(),
        expected_emails=(),
        expected_urls=(),
        expected_mentions=("@www.dummyhub.com",),
        expected_words=("didn", "have", "pickles"),
        expected_tokens="didn\x1fhave\x1fpickles",
    ),

    TokenizerCase(
        name="mention glued to bare domain with path",
        text="@promoyoutube.com/deal hello",
        expected_hashtags=(),
        expected_mentions=(
            "@promoyoutube.com/deal",
        ),
        expected_urls=(),
        expected_tokens="hello",
        expected_words=("hello",),
        expected_emails=(),
    )
)

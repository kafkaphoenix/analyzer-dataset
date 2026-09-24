from tests.scenarios.tokenizer_cases import TokenizerCase

EMAIL_CASES = (
    TokenizerCase(
        name="simple email is not mention",
        text="contact john@example.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john@example.com",),
    ),

    TokenizerCase(
        name="email with dotted local part",
        text="contact john.smith@example.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john.smith@example.com",),
    ),

    TokenizerCase(
        name="email with plus addressing",
        text="contact john+test@example.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john+test@example.com",),
    ),

    TokenizerCase(
        name="email with underscore in local part",
        text="contact john_test@example.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john_test@example.com",),
    ),

    TokenizerCase(
        name="email with hyphen in local part",
        text="contact john-test@example.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john-test@example.com",),
    ),

    TokenizerCase(
        name="email with subdomain",
        text="contact john@example.co.uk now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john@example.co.uk",),
    ),

    TokenizerCase(
        name="email with hyphen in domain",
        text="contact john@my-example.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john@my-example.com",),
    ),

    TokenizerCase(
        name="email with numeric domain",
        text="contact john@example123.com now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john@example123.com",),
    ),

    TokenizerCase(
        name="email with uppercase letters",
        text="contact JOHN@EXAMPLE.COM now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("JOHN@EXAMPLE.COM",),
    ),

    TokenizerCase(
        name="email followed by punctuation",
        text="contact john@example.com, thanks",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "thanks"),
        expected_tokens="contact\x1fthanks",
        expected_emails=("john@example.com",),
    ),

    TokenizerCase(
        name="email is not mention",
        text="@john@example.com",
        expected_hashtags=(),
        expected_mentions=("@john","@example.com"),
        expected_words=(),
        expected_tokens="",
        expected_emails=(),
    ),

    TokenizerCase(
        name="email domain containing incidental www. substring",
        text="Contact edit@2rawww.japan now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_emails=("edit@2rawww.japan",),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
    ),

    TokenizerCase(
        name="mention containing email-like domain",
        text="Contact @s.s_l.143 now",
        expected_hashtags=(),
        expected_mentions=("@s.s_l.143",),
        expected_emails=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
    ),
)

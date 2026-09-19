
from tests.fixtures.tokenizer_cases import TokenizerCase

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
        name="email with subdomain",
        text="contact john@example.co.uk now",
        expected_hashtags=(),
        expected_mentions=(),
        expected_words=("contact", "now"),
        expected_tokens="contact\x1fnow",
        expected_emails=("john@example.co.uk",),
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
)

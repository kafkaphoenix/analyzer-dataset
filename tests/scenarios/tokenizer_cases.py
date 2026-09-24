from __future__ import annotations

from dataclasses import dataclass

_TRAILING_URL_PUNCTUATION = ".,!?;:)]}"


@dataclass(frozen=True)
class TokenizerCase:
    name: str
    text: str
    expected_hashtags: tuple[str, ...]
    expected_words: tuple[str, ...]
    expected_tokens: str
    expected_mentions: tuple[str, ...] = ()
    expected_emails: tuple[str, ...] = ()
    expected_urls: tuple[str, ...] = ()


def strip_trailing_url_punctuation(
    url: str,
) -> str:
    while url and url[-1] in _TRAILING_URL_PUNCTUATION:
        char = url[-1]

        if char == ")":
            if url.count("(") >= url.count(")"):
                break
        elif char == "]":
            if url.count("[") >= url.count("]"):
                break
        elif char == "}":
            if url.count("{") >= url.count("}"):
                break

        url = url[:-1]

    return url


def strip_leading_url_boundary(
    url: str,
) -> str:
    """
    URL_SCHEME_PATTERN's "www." alternative and BARE_DOMAIN_PATTERN's
    optional-path literals (youtube.com, youtu.be, tinyurl.com,
    linktr.ee, amzn.to) require a left-boundary guard in tokenizer.py:
    start-of-string or a single non-alnum, non-underscore character.
    None of RE2/Rust-regex/libcudf support lookbehind, so that guard
    character is consumed as part of the match rather than asserted
    separately -- harmless for production, which only ever replaces
    the whole match with a single space, but this diagnostic reports
    the matched text itself, so a match like " www.example.com" would
    otherwise carry a stray leading character that was never part of
    the real URL.

    Strips at most one leading character -- exactly what the guard
    can ever consume. A match at true string start (no guard char
    consumed) or an https?:// match (no guard needed at all, since
    EMAIL_DOMAIN's character class can't contain ':' or '/') already
    starts with an alnum character and is left untouched.
    """
    if url and not (
        url[0].isalnum()
        or url[0] == "_"
    ):
        return url[1:]

    return url
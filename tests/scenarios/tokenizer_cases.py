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
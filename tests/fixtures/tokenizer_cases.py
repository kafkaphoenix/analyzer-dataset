from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class TokenizerCase:
    name: str
    text: str
    expected_hashtags: tuple[str, ...]
    expected_words: tuple[str, ...]
    expected_tokens: str
    expected_mentions: tuple[str, ...] = ()
    expected_emails: tuple[str, ...] = ()

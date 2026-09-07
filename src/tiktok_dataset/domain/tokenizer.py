from __future__ import annotations

import re

URL_PATTERN = r"https?://\S+|www\.\S+"
YOUTUBE_PATTERN = r"youtu\.be/\S+"
HASHTAG_PATTERN = r"#\w+"

CLEAN_PATTERN = f"{URL_PATTERN}|{YOUTUBE_PATTERN}|{HASHTAG_PATTERN}"

WORD_PATTERN = r"[a-z]{3,}"

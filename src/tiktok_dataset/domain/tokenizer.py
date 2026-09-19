from __future__ import annotations

"""
Shared tokenization patterns for the cuDF, DuckDB, and Polars (CPU/GPU)
query engines.
Design intent: each engine still runs its own native regex/string
ops, but the *pattern strings* and the *character-folding step*
are centralized here so the four engines are working from the same
definitions rather than four independently-drifting copies. RE2
(DuckDB), Rust's `regex`crate (Polars), and libcudf's regex engine
each interpret Unicode character classes differently, so getting
these four in agreement required actually testing cross-engine output
on real data.
See benchmarks/tokenizer_mismatch_finder.py, which scans the full dataset
and saves every sentence the engines disagree on to
results/tokenizer_mismatches.parquet. Also see benchmark/english_tokenizer_mismatch_finder.py.
, which scans the full dataset for English tokenization mismatches.
"""

# --------------------------------------------------------------------
# URLs / known link-shortener and video-platform domains
# --------------------------------------------------------------------
# An explicit RFC 3986-ish character class instead of `\S+`. `\S+`
# depends on each engine's own definition of "whitespace", and those
# disagree for non-ASCII characters (e.g. U+00A0 NBSP counted as
# non-whitespace by RE2 but as whitespace by Rust's regex crate) --
# that let a greedy `\S+` URL match run through an NBSP and swallow
# the next real word on DuckDB specifically. An explicit literal
# class has no such ambiguity: every engine matches exactly these
# characters and nothing else.
#
# Apostrophe (') is deliberately excluded even though it's a valid
# (if rare) URL character: CLEAN_PATTERN_DUCKDB gets interpolated
# into a single-quoted SQL string, and a literal `'` in the pattern
# would break that string. Worst case a URL containing an apostrophe
# stops matching one character early -- narrower than `\S+`.
_URL_CHARS = r"[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]"

# Scheme-based URLs (http://, https://, www.) are cheap to match: every
# engine's regex engine can key off the fixed `http`/`www` literal at the
# start of the alternative, so this half of URL_PATTERN never showed up
# as a cost problem on any engine. Split out as its own public name (not
# just an inline half of URL_PATTERN) so the cuDF engine can run this
# half against every row while running BARE_DOMAIN_PATTERN below only
# against a pre-filtered subset -- see repository/engines/cudf.py.
URL_SCHEME_PATTERN = rf"https?://{_URL_CHARS}+|www\.{_URL_CHARS}+"

# t.co, bit.ly, and goo.gl are short/generic-looking enough that they
# can in principle collide with an incidental substring of ordinary
# text (e.g. a hand-typed "...want.company..." with no space after
# the period). No engine here supports lookbehind, so we can't cheaply
# assert "not preceded by a letter" the way a lookbehind-capable
# engine would, and `\s`/`\b`-based alternatives reintroduce the same
# cross-engine whitespace disagreement called out above for `\S+`.
# Instead: a real shortlink from these three is never functional
# without its slug, so the path segment is REQUIRED for these three
# specifically, ruling out the bare "t.co" (nothing after it) case.
# The remaining domains are long/distinctive enough that a bare
# mention (no path) is still safe to treat as a link.
_BARE_DOMAINS_REQUIRE_PATH = (
    r"bit\.ly",
    r"t\.co",
    r"goo\.gl",
)

# `youtube\.com` carries an optional `m\.` prefix in one alternative
# (rather than two separate entries) so a mobile link is consumed as
# a single match instead of leaving a stray "m." behind.
_BARE_DOMAINS_OPTIONAL_PATH = (
    r"(?:m\.)?youtube\.com",
    r"youtu\.be",
    r"tinyurl\.com",
    r"linktr\.ee",
    r"amzn\.to",
)

# Public (not underscore-prefixed): an alternation of literal domains
# with no common anchor character is the expensive half of URL_PATTERN
# on cuDF specifically -- libcudf's regex engine can't apply any
# literal-prefix fast path to it, so it falls back to evaluating the
# full automaton at every character position of every row. The cuDF
# engine imports this directly so it can run it only against a
# pre-filtered subset of rows instead of the full column (see
# repository/engines/cudf.py). Keep this the single source of truth for
# the bare-domain regex text -- do not fork a cuDF-local copy of it, or
# the four engines drift again, which is exactly what this module
# exists to prevent.
BARE_DOMAIN_PATTERN = (
    rf"(?:{'|'.join(_BARE_DOMAINS_REQUIRE_PATH)})/{_URL_CHARS}+"
    rf"|(?:{'|'.join(_BARE_DOMAINS_OPTIONAL_PATH)})(?:/{_URL_CHARS}*)?"
)

# Unchanged value for DuckDB/Polars (and for anything that doesn't care
# about the scheme/bare-domain split) -- built from the two pieces above
# rather than redefined separately, so there's no way for this to drift
# from what those two now say.
URL_PATTERN = rf"{URL_SCHEME_PATTERN}|{BARE_DOMAIN_PATTERN}"

# --------------------------------------------------------------------
# Hashtags
# --------------------------------------------------------------------
# Ref: https://www.unicode.org/reports/tr31/tr31-39.html?utm_source=chatgpt.com#hashtag_identifiers
# Ref: https://en.wikipedia.org/wiki/Hashtag
# Hashtags legitimately contain letters from any script -- Burmese,
# Devanagari, Thai, Cyrillic, decorative "fancy font" Unicode, etc.
# `\w` is the wrong tool for this: RE2's `\w` is ASCII-only by default,
# and libcudf's `\w`, while Unicode-aware, covers a much narrower set of
# scripts than either RE2 or Rust's `regex` crate.
#
# For Polars/DuckDB, `\p{L}\p{N}_` (explicit Unicode property
# escapes) sidesteps RE2's ASCII-only `\w` shorthand entirely and
# was verified byte-for-byte against DuckDB on every real mismatch
# case found in the corpus -- duckdb_vs_polars is now 0 across the
# full dataset. `\p{M}` (combining marks) was tried too at one point
# and dropped: nothing in the corpus-driven testing showed it was
# needed, and leaving it out keeps the class smaller.

# A negated/exclusion-based version of this pattern was tried first
# (match anything that ISN'T whitespace/punctuation, instead of
# enumerating what a hashtag IS) specifically to avoid needing to
# know libcudf's Unicode coverage at all. It was rejected: without
# real whitespace between hashtags, the match doesn't stop at emoji
# either, and it swallowed entire captions.

# Polars' regex Unicode tables treat U+13F64 as \p{L}/\p{N},
# while DuckDB and cuDF stop the hashtag at this character.
# So Polars needs to explicitly exclude this character from its hashtag matches.
POLARS_REGEX_COMPATIBILITY_DELIMITERS = "\U00013f64"

HASHTAG_PATTERN_DUCKDB = r"#[\p{L}\p{M}\p{N}_]+"

HASHTAG_PATTERN_POLARS = (
    rf"#[\p{{L}}\p{{M}}\p{{N}}_&&[^{POLARS_REGEX_COMPATIBILITY_DELIMITERS}]]+"
)

# cuDF's regex engine doesn't support `\p{...}` syntax at all -- it
# doesn't error, it silently matches nothing. It also doesn't accept
#  `\U0001D400`-style escape sequences inside a character class --
# those are silently ignored too.
# What *does* work: splicing the actual UTF-8 characters in as
# literal range bounds, which only requires the engine to handle
# ordinary multi-byte range endpoints, not parse an escape sequence.
#
# These four ranges are the specific scripts the real dataset
# surfaced through several rounds of corpus-driven testing. This list is NOT
# an exhaustive Unicode letter table -- it's whatever this dataset
# happened to contain. A future data refresh could surface another
# script-specific gap the same shape as these; if it does, extend
# this list the same way.
_MATH_ALPHANUMERIC = "\U0001d400-\U0001d7ff"
_EGYPTIAN_HIEROGLYPHS = "\U00013000-\U0001342f"
_CUNEIFORM = "\U00012000-\U000123ff"
_BAMUM = "\U00016800-\U00016a3f"
_LINEAR_B = "\U00010000-\U0001007f"
_DEVANAGARI = "\u0900-\u097f"
_BENGALI = "\u0980-\u09ff"
_TAMIL = "\u0b80-\u0bff"
_TELUGU = "\u0c00-\u0c7f"
_KANNADA = "\u0c80-\u0cff"
_MALAYALAM = "\u0d00-\u0d7f"
_THAI = "\u0e00-\u0e7f"
HASHTAG_PATTERN_CUDF = f"#[\\w{_MATH_ALPHANUMERIC}{_EGYPTIAN_HIEROGLYPHS}{_CUNEIFORM}{_BAMUM}{_LINEAR_B}{_DEVANAGARI}{_BENGALI}{_TAMIL}{_TELUGU}{_KANNADA}{_MALAYALAM}{_THAI}]+"

# --------------------------------------------------------------------
# Email addresses
# --------------------------------------------------------------------
_EMAIL_LOCAL_CHARS = r"[A-Za-z0-9_+-]"
EMAIL_LOCAL = rf"{_EMAIL_LOCAL_CHARS}+(?:\.{_EMAIL_LOCAL_CHARS}+)*"

_EMAIL_DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
EMAIL_DOMAIN = rf"{_EMAIL_DOMAIN_LABEL}(?:\.{_EMAIL_DOMAIN_LABEL})+"

EMAIL_PATTERN = rf"{EMAIL_LOCAL}@{EMAIL_DOMAIN}"

# --------------------------------------------------------------------
# @ mentions
# --------------------------------------------------------------------
# TikTok usernames allow letters, numbers, underscore, and period --
# but NOT a leading, trailing, or doubled period. Rather than encode
# that as a lookaround (unsupported by RE2, Rust's regex crate, and
# libcudf alike), it falls out for free from a "segments joined by a
# single period" structure: [segment]+(?:\.[segment]+)*. A trailing
# or leading period can never match (the \. group always requires a
# following non-empty segment, and the pattern must start with one);
# a doubled period simply ends the match early, same as the existing
# "stop at the first non-matching character" behavior everywhere else
# in this module (see the emoji/symbol hashtag-boundary cases).
_MENTION_SEGMENT = r"[\p{L}\p{N}_]"
MENTION_PATTERN_DUCKDB = rf"@{_MENTION_SEGMENT}+(?:\.{_MENTION_SEGMENT}+)*"  # DuckDB

# Same U+13F64 carve-out as HASHTAG_PATTERN_POLARS -- Polars' Unicode
# tables classify it as \p{L}/\p{N} where DuckDB/cuDF don't.
_MENTION_SEGMENT_POLARS = (
    rf"[\p{{L}}\p{{N}}_&&[^{POLARS_REGEX_COMPATIBILITY_DELIMITERS}]]"
)
MENTION_PATTERN_POLARS = (
    rf"@{_MENTION_SEGMENT_POLARS}+(?:\.{_MENTION_SEGMENT_POLARS}+)*"
)

# Same \w + explicit script-range splice as HASHTAG_PATTERN_CUDF,
# since libcudf's regex engine silently no-ops on \p{...} syntax.
_MENTION_CHARS_CUDF = (
    rf"\w{_MATH_ALPHANUMERIC}{_EGYPTIAN_HIEROGLYPHS}{_CUNEIFORM}{_BAMUM}{_LINEAR_B}"
)
MENTION_PATTERN_CUDF = (
    rf"@[{_MENTION_CHARS_CUDF}]+(?:\.[{_MENTION_CHARS_CUDF}]+)*"
)

CLEAN_PATTERN_POLARS = (
    f"{URL_PATTERN}|"
    f"{EMAIL_PATTERN}|"
    f"{MENTION_PATTERN_POLARS}|"
    f"{HASHTAG_PATTERN_POLARS}|"
    f"{POLARS_REGEX_COMPATIBILITY_DELIMITERS}"
)
CLEAN_PATTERN_DUCKDB = (
    f"{URL_PATTERN}|"
    f"{EMAIL_PATTERN}|"
    f"{MENTION_PATTERN_DUCKDB}|"
    f"{HASHTAG_PATTERN_DUCKDB}"

)
CLEAN_PATTERN_CUDF = (
    f"{URL_PATTERN}|"
    f"{EMAIL_PATTERN}|"
    f"{MENTION_PATTERN_CUDF}|"
    f"{HASHTAG_PATTERN_CUDF}"
)

# --------------------------------------------------------------------
# Words
# --------------------------------------------------------------------
# ASCII lowercase only, on purpose: the English dictionary
# (repository/vocabulary.py) is ASCII-only, so nothing broader than
# this can ever survive the dictionary join anyway. This also
# depends on lowering happening via ASCII_LOWER_MAP (below), not
# each engine's own `lower()` -- see that section for why.
WORD_PATTERN = r"[a-z]{3,}"
WORD_PATTERN_DUCKDB = WORD_PATTERN
WORD_PATTERN_CUDF = WORD_PATTERN

# --------------------------------------------------------------------
# Case folding
# --------------------------------------------------------------------
# Deliberately NOT each engine's native `lower()`. DuckDB's `lower()`
# does *simple* Unicode case mapping (always one codepoint in, one
# codepoint out); Polars/Rust's `to_lowercase()` does *full* case
# mapping, which can expand one codepoint into several. Turkish
# capital I-with-dot (U+0130): DuckDB folds it to plain "i" (one codepoint),
#  Rust folds it to "i" + a combining dot above (two codepoints) -- per Unicode's own
# SpecialCasing.txt, both are "correct" by different standards, but
# they don't agree with each other. With WORD_PATTERN restricted to
# `[a-z]`, that extra combining-mark codepoint silently split
# "izmir" into a dropped 1-character "i" and a leaked "zmir" on
# Polars/cuDF, while DuckDB kept "izmir" intact -- a real,
# non-obvious source of cross-engine drift that had nothing to do
# with scripts or hashtags.
#
# Using an explicit, fixed A-Z -> a-z translation table instead of
# native `lower()` sidesteps the whole simple-vs-full case-folding
# question: it's a dumb, deterministic, engine-agnostic character
# substitution, not a semantic Unicode operation, so all four
# engines necessarily agree. Non-ASCII uppercase letters (İ, É, ...)
# are left untouched rather than folded -- which is fine, since
# WORD_PATTERN was never going to match them either way, folded or
# not.
ASCII_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ASCII_LOWER = "abcdefghijklmnopqrstuvwxyz"

ASCII_LOWER_MAP = dict(zip(ASCII_UPPER, ASCII_LOWER, strict=False))
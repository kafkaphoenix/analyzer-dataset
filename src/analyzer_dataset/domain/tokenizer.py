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
_URL_CHARS = r"[A-Za-z0-9._~:/?#@!$&()*+,;=%…-]"

# Left-boundary guard for literal trigger strings that require no
# following character to complete a match (www., and the bare-domain
# literals below that don't require a path). Without this, the literal
# can match wherever it happens to appear as a coincidental substring --
# e.g. "www." inside a valid two-label email domain like "2rawww.japan",
# or "youtube.com" inside "fooyoutube.combar" -- which is structurally
# possible for these specifically because "." is a valid domain-label
# separator, so the literal can sit fully inside another pattern's
# match with nothing to stop it.
#
# No lookbehind support in RE2/Rust-regex/libcudf, so the boundary
# character is consumed as part of the match rather than asserted
# separately. That's harmless here: the boundary is required to be a
# non-word character (not alnum, not underscore), so it was never
# going to be part of a WORD_PATTERN match anyway, and folding it into
# a single-space replacement doesn't merge or split anything that
# wasn't already going to be separated.
#
# https?:// and the REQUIRE_PATH literals (bit.ly/t.co/goo.gl) don't
# need this guard: EMAIL_DOMAIN's character class contains neither
# ':' nor '/' nor '#', so none of those can structurally appear
# embedded inside a valid email domain in the first place.
# Bare URLs must not start immediately after '@', because '@' is
# either an email delimiter or a mention marker.
_URL_CHARS = r"[A-Za-z0-9._~:/?#@!$&()*+,;=%…-]"

# Bare URLs must not start immediately after '@', because '@' is
# either an email delimiter or a mention marker.
_TOKEN_BOUNDARY = r"(?:^|[^A-Za-z0-9_@])"

URL_SCHEME_PATTERN = (
    rf"https?://{_URL_CHARS}+"
    rf"|{_TOKEN_BOUNDARY}www\.{_URL_CHARS}+"
)

_BARE_DOMAINS_REQUIRE_PATH = (
    r"bit\.ly",
    r"t\.co",
    r"goo\.gl",
)

_BARE_DOMAINS_OPTIONAL_PATH = (
    rf"{_TOKEN_BOUNDARY}(?:m\.)?youtube\.com",
    rf"{_TOKEN_BOUNDARY}youtu\.be",
    rf"{_TOKEN_BOUNDARY}tinyurl\.com",
    rf"{_TOKEN_BOUNDARY}linktr\.ee",
    rf"{_TOKEN_BOUNDARY}amzn\.to",
)

BARE_DOMAIN_PATTERN = (
    rf"(?:{'|'.join(_BARE_DOMAINS_REQUIRE_PATH)})/{_URL_CHARS}+"
    rf"|(?:{'|'.join(_BARE_DOMAINS_OPTIONAL_PATH)})(?:/{_URL_CHARS}*)?"
)

URL_PATTERN = rf"{URL_SCHEME_PATTERN}|{BARE_DOMAIN_PATTERN}"

# Hashtags continue until whitespace or another '#' is encountered.
# Any other character is valid inside a hashtag, including ASCII and
# Unicode punctuation, symbols, and emoji.
#
#   #hello!world           -> #hello!world
#   #hello-world           -> #hello-world
#   #،like                 -> #،like
#   #hello©world           -> #hello©world
#   #hello😀world           -> #hello😀world
#   #maharastra𓽤khudko    -> #maharastra𓽤khudko
#   #hola#hola             -> #hola, #hola
#   #hello world           -> #hello, world

# Unicode whitespace that must terminate a hashtag.
# Keep this explicit because DuckDB/RE2 does not classify all Unicode
# whitespace characters the same way as Polars/Rust regex and cuDF.
_HASHTAG_WHITESPACE = (
    " "
    "\t"
    "\n"
    "\r"
    "\f"
    "\v"
    "\u0085"  # NEXT LINE
    "\u00a0"  # NO-BREAK SPACE
    "\u1680"  # OGHAM SPACE MARK
    "\u2000"  # EN QUAD
    "\u2001"  # EM QUAD
    "\u2002"  # EN SPACE
    "\u2003"  # EM SPACE
    "\u2004"  # THREE-PER-EM SPACE
    "\u2005"  # FOUR-PER-EM SPACE
    "\u2006"  # SIX-PER-EM SPACE
    "\u2007"  # FIGURE SPACE
    "\u2008"  # PUNCTUATION SPACE
    "\u2009"  # THIN SPACE
    "\u200a"  # HAIR SPACE
    "\u2028"  # LINE SEPARATOR
    "\u2029"  # PARAGRAPH SEPARATOR
    "\u202f"  # NARROW NO-BREAK SPACE
    "\u205f"  # MEDIUM MATHEMATICAL SPACE
    "\u3000"  # IDEOGRAPHIC SPACE
)

HASHTAG_PATTERN_DUCKDB = rf"#[^{_HASHTAG_WHITESPACE}#@]+"
HASHTAG_PATTERN_POLARS = r"#[^\s#@]+"
HASHTAG_PATTERN_CUDF = r"#[^\s#@]+"

# --------------------------------------------------------------------
# Email addresses
# --------------------------------------------------------------------
_EMAIL_LOCAL_CHARS = r"[A-Za-z0-9_+-]"
EMAIL_LOCAL = rf"{_EMAIL_LOCAL_CHARS}+(?:\.{_EMAIL_LOCAL_CHARS}+)*"

_EMAIL_DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
EMAIL_DOMAIN = rf"{_EMAIL_DOMAIN_LABEL}(?:\.{_EMAIL_DOMAIN_LABEL})+"

EMAIL_PATTERN = rf"(?:^|[^@A-Za-z0-9_]){EMAIL_LOCAL}@{EMAIL_DOMAIN}"

# The trailing negative lookahead prevents partial matches such as
# "foo@example.com_extra", but libcudf's regex engine does not support
# lookahead assertions, so this cannot be used in the cuDF regex pattern.
# EMAIL_PATTERN = rf"{EMAIL_LOCAL}@{EMAIL_DOMAIN}(?![A-Za-z0-9_.+-])"

# similarly this fix some edge cases but taking 8 sec more
# EMAIL_PATTERN = (
#     rf"(?:^|[^@A-Za-z0-9_#])"
#     rf"{EMAIL_LOCAL}@{EMAIL_DOMAIN}"
# )

# --------------------------------------------------------------------
# @ mentions
# --------------------------------------------------------------------
# Same boundary rule as hashtags: @ followed by a run of anything
# that isn't whitespace or another @. Replaces the old per-engine
# \p{L}\p{N}_ / explicit-script-range approach -- that required
# manually whitelisting every historic Unicode block that could
# appear in a username (Linear A/B, Old Italic, Warang Citi,
# Mongolian, Elbasan, Caucasian Albanian, ...) for cuDF specifically,
# since libcudf's regex has no \p{L}. Every missed block was a
# silent cuDF-only mismatch -- consuming until a boundary character
# sidesteps script coverage entirely instead of enumerating it.
#
# Uses _HASHTAG_WHITESPACE rather than native \s for DuckDB, for the
# same reason HASHTAG_PATTERN_DUCKDB does: RE2's \s and Rust/libcudf's
# \s don't agree on which code points count as whitespace.
MENTION_PATTERN_DUCKDB = rf"@[^{_HASHTAG_WHITESPACE}@#]+"
MENTION_PATTERN_POLARS = r"@[^\s@#]+"
MENTION_PATTERN_CUDF = r"@[^\s@#]+"

CLEAN_PATTERN_POLARS = f"{URL_PATTERN}|{EMAIL_PATTERN}|{MENTION_PATTERN_POLARS}|{HASHTAG_PATTERN_POLARS}"
CLEAN_PATTERN_DUCKDB = f"{URL_PATTERN}|{EMAIL_PATTERN}|{MENTION_PATTERN_DUCKDB}|{HASHTAG_PATTERN_DUCKDB}"
CLEAN_PATTERN_CUDF = f"{URL_PATTERN}|{EMAIL_PATTERN}|{MENTION_PATTERN_CUDF}|{HASHTAG_PATTERN_CUDF}"

# --------------------------------------------------------------------
# Words
# --------------------------------------------------------------------
# ASCII lowercase only, on purpose: the English dictionary
# (repository/vocabulary.py) is ASCII-only, so nothing broader than
# this can ever survive the dictionary join anyway. This also
# depends on lowering happening via ASCII_LOWER_MAP (below), not
# each engine's own `lower()` -- see that section for why.
WORD_PATTERN = r"[a-z]{3,}"
WORD_PATTERN_POLARS = WORD_PATTERN
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

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
_URL_CHARS = r"[A-Za-z0-9._~:/?#@!$&()*+,;=%…-]"

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

EMAIL_PATTERN = rf"{EMAIL_LOCAL}@{EMAIL_DOMAIN}"

# The trailing negative lookahead prevents partial matches such as
# "foo@example.com_extra", but libcudf's regex engine does not support
# lookahead assertions, so this cannot be used in the cuDF regex pattern.
# EMAIL_PATTERN = rf"{EMAIL_LOCAL}@{EMAIL_DOMAIN}(?![A-Za-z0-9_.+-])"

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

# Better performance if regex are applied separately rather than combined for cuDF.
#CLEAN_PATTERN_CUDF = f"{EMAIL_PATTERN}|{URL_PATTERN}|{MENTION_PATTERN_CUDF}|{HASHTAG_PATTERN_CUDF}"

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

from __future__ import annotations

from pathlib import Path

import cudf
import polars as pl
import pyarrow as pa
import pylibcudf as plc

from analyzer_dataset.domain.data_quality import (
    CORRUPTED_PAYLOAD_PATTERN,
)
from analyzer_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    BARE_DOMAIN_PATTERN,
    EMAIL_PATTERN,
    HASHTAG_PATTERN_CUDF,
    MENTION_PATTERN_CUDF,
    URL_SCHEME_PATTERN,
    WORD_PATTERN_CUDF,
)
from analyzer_dataset.repository.vocabulary import (
    load_english_words,
)
from analyzer_dataset.usecase.query import ProgressReporter

ENGINE = "cudf"

# Cheap literal substrings used only to build candidate-row masks.
#
# These are deliberately over-inclusive. The actual bare-domain regex
# remains responsible for deciding whether a bare domain is a match.
_BARE_DOMAIN_LITERALS = (
    "bit.ly",
    "t.co",
    "goo.gl",
    "youtube.com",
    "youtu.be",
    "tinyurl.com",
    "linktr.ee",
    "amzn.to",
)

_REGEX_DEFAULT_FLAGS = 0

_REPLACEMENT_SPACE = plc.Scalar.from_arrow(
    pa.scalar(
        " ",
        type=pa.string(),
    )
)

_EMPTY_REPLACEMENT = plc.Scalar.from_arrow(
    pa.scalar(
        "",
        type=pa.string(),
    )
)

_CORRUPTED_PAYLOAD_PROGRAM = plc.strings.regex_program.RegexProgram.create(
    CORRUPTED_PAYLOAD_PATTERN,
    _REGEX_DEFAULT_FLAGS,
)

_EMAIL_PROGRAM = plc.strings.regex_program.RegexProgram.create(
    EMAIL_PATTERN,
    _REGEX_DEFAULT_FLAGS,
)

_MENTION_PROGRAM = plc.strings.regex_program.RegexProgram.create(
    MENTION_PATTERN_CUDF,
    _REGEX_DEFAULT_FLAGS,
)

_URL_SCHEME_PROGRAM = plc.strings.regex_program.RegexProgram.create(
    URL_SCHEME_PATTERN,
    _REGEX_DEFAULT_FLAGS,
)

_BARE_DOMAIN_PROGRAM = plc.strings.regex_program.RegexProgram.create(
    BARE_DOMAIN_PATTERN,
    _REGEX_DEFAULT_FLAGS,
)

_HASHTAG_PROGRAM = plc.strings.regex_program.RegexProgram.create(
    HASHTAG_PATTERN_CUDF,
    _REGEX_DEFAULT_FLAGS,
)

def clean_desc_cudf(
    desc: cudf.Series,
) -> cudf.Series:
    """
    Apply the native cuDF production cleaning pipeline.

    Order:

    1. Remove known corrupted binary payloads.
    2. ASCII lowercase A-Z.
    3. Remove scheme-based URLs.
    4. Remove bare domains on candidate rows only.
    5. Remove emails.
    6. Remove @mentions.
    7. Remove hashtags.

    Unlike Polars/DuckDB -- which compile everything into one
    alternation and resolve overlaps by leftmost match, making their
    listed order mostly cosmetic -- cuDF applies each pattern as its
    own sequential pass over already-modified text. What an earlier
    pass consumes is gone before a later pass ever sees it, so this
    order is NOT cosmetic and NOT just "matching" the other engines;
    it is its own contract, driven by two rules:

    - Narrower character classes run before broader ones. URL_SCHEME
      and BARE_DOMAIN only ever match ASCII URL characters; MENTION
      and HASHTAG match almost anything except whitespace/@/#,
      including every emoji and every Unicode script. Running
      mention/hashtag first lets that broad class swallow a URL glued
      directly onto it (common in social media bios: "@promobit.ly/deal")
      plus whatever real word follows through an emoji separator,
      since nothing but whitespace stops it.
    - URL_SCHEME runs before BARE_DOMAIN, and BARE_DOMAIN runs before
      EMAIL: _URL_CHARS includes '@', '.', and '/', so an email-
      shaped substring inside a URL path is correctly swallowed
      whole by the URL patterns. Reversing this lets EMAIL consume
      the "user@site.co" portion of "bit.ly/user@site.co" first,
      stripping the path bit.ly/t.co/goo.gl's REQUIRE_PATH check
      depends on -- causing the match to fail and leaking "bit" or
      "goo" as a spurious 3+ letter word.
    - EMAIL still runs before MENTION: an email's '@' is not itself a
      mention trigger, but MENTION's pattern doesn't know that -- it
      matches starting AT any '@' regardless of what precedes it, so
      "user@gmail.com" would otherwise be cut to "@gmail.com",
      stranding "user" as a leaked word.

    Bare domains are handled separately because applying their
    relatively expensive regex to every row is avoided through a
    cheap candidate-row mask.

    The same function is used by the production query and by the
    tokenizer differential diagnostic so that the diagnostic cannot
    accidentally test a different cuDF implementation.
    """
    original_index = desc.index

    # ---------------------------------------------------------------
    # 1. Remove known corrupted binary payloads.
    # ---------------------------------------------------------------
    col, meta = desc.to_pylibcudf()

    col = plc.strings.replace_re.replace_re(
        col,
        _CORRUPTED_PAYLOAD_PROGRAM,
        _EMPTY_REPLACEMENT,
    )

    desc = cudf.Series.from_pylibcudf(
        col,
        metadata=meta,
    )
    desc.index = original_index

    # ---------------------------------------------------------------
    # 2. ASCII lowercase A-Z.
    # ---------------------------------------------------------------
    desc = desc.str.translate(ASCII_LOWER_MAP)

    # ---------------------------------------------------------------
    # 3. Remove scheme-based URLs.
    # ---------------------------------------------------------------
    col, meta = desc.to_pylibcudf()

    col = plc.strings.replace_re.replace_re(
        col,
        _URL_SCHEME_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    desc = cudf.Series.from_pylibcudf(
        col,
        metadata=meta,
    )
    desc.index = original_index

    # ---------------------------------------------------------------
    # 4. Remove bare domains only on candidate rows.
    # ---------------------------------------------------------------
    bare_domain_mask = None

    for literal in _BARE_DOMAIN_LITERALS:
        hit = desc.str.contains(
            literal,
            regex=False,
        )

        bare_domain_mask = hit if bare_domain_mask is None else bare_domain_mask | hit

    if bare_domain_mask is not None and bare_domain_mask.any():
        subset = desc.loc[bare_domain_mask]

        sub_col, sub_meta = subset.to_pylibcudf()

        sub_col = plc.strings.replace_re.replace_re(
            sub_col,
            _BARE_DOMAIN_PROGRAM,
            _REPLACEMENT_SPACE,
        )

        replaced = cudf.Series.from_pylibcudf(
            sub_col,
            metadata=sub_meta,
        )
        replaced.index = subset.index

        desc.loc[bare_domain_mask] = replaced

    # ---------------------------------------------------------------
    # 5. Remove emails.
    # ---------------------------------------------------------------
    col, meta = desc.to_pylibcudf()

    col = plc.strings.replace_re.replace_re(
        col,
        _EMAIL_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    desc = cudf.Series.from_pylibcudf(
        col,
        metadata=meta,
    )
    desc.index = original_index

    # ---------------------------------------------------------------
    # 6. Remove @mentions.
    # ---------------------------------------------------------------
    col, meta = desc.to_pylibcudf()

    col = plc.strings.replace_re.replace_re(
        col,
        _MENTION_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    desc = cudf.Series.from_pylibcudf(
        col,
        metadata=meta,
    )
    desc.index = original_index

    # ---------------------------------------------------------------
    # 7. Remove hashtags.
    # ---------------------------------------------------------------
    col, meta = desc.to_pylibcudf()

    col = plc.strings.replace_re.replace_re(
        col,
        _HASHTAG_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    desc = cudf.Series.from_pylibcudf(
        col,
        metadata=meta,
    )
    desc.index = original_index

    return desc


class GPUCUDFQuery:
    """
    Native cuDF implementation.

    Parquet reading, tokenization, dictionary filtering and
    aggregation are performed entirely on the GPU using libcudf
    and cuDF.
    """

    def __init__(
        self,
        parquet_path: Path,
        english_words_path: Path,
        english_stopwords_path: Path,
        min_word_length: int,
        top_k: int,
        chunk_read_limit: int,
    ):
        self.parquet_path = parquet_path
        self.english_words_path = english_words_path
        self.english_stopwords_path = english_stopwords_path
        self.min_word_length = min_word_length
        self.top_k = top_k
        self.chunk_read_limit = chunk_read_limit

    @staticmethod
    def _process_dataframe(
        df: cudf.DataFrame,
        english_words: cudf.DataFrame,
    ) -> cudf.DataFrame | None:
        """
        Tokenize text, filter against the vocabulary, and aggregate
        views per batch on the GPU.
        """
        df = df.dropna(
            subset=[
                "desc",
                "views",
            ]
        )

        if len(df) == 0:
            return None

        # clean_desc_cudf() preserves the original index through all
        # pylibcudf round-trips, which keeps desc aligned with views.
        desc = clean_desc_cudf(df["desc"])

        # Extract unique tokens per description.
        words = desc.str.findall(WORD_PATTERN_CUDF).list.unique()

        df = cudf.DataFrame(
            {
                "views": df["views"],
                "word": words,
            }
        )

        # Explode arrays into individual rows.
        df = df.explode(
            "word",
            ignore_index=True,
        ).dropna(subset=["word"])

        if len(df) == 0:
            return None

        # Filter tokens against the English vocabulary.
        df = df.merge(
            english_words,
            on="word",
            how="inner",
        )

        if len(df) == 0:
            return None

        # Pre-aggregate views per word to minimize the final merge.
        #
        # cuDF returns int64 from the sum even though views are uint64,
        # so explicitly restore uint64.
        return (
            df.groupby(
                "word",
                sort=False,
            )["views"]
            .sum()
            .reset_index(name="total_views")
            .astype(
                {
                    "total_views": "uint64",
                }
            )
        )

    def _process_stream(
        self,
        english_words: cudf.DataFrame,
        progress: ProgressReporter | None = None,
    ) -> cudf.DataFrame:
        """
        Stream Parquet chunks via pylibcudf, updating progress and
        collecting GPU partial sums.
        """
        source = plc.io.SourceInfo([str(self.parquet_path)])

        options = (
            plc.io.parquet.ParquetReaderOptions.builder(source)
            .column_names(
                [
                    "views",
                    "desc",
                ]
            )
            .build()
        )

        reader = plc.io.parquet.ChunkedParquetReader(
            options,
            chunk_read_limit=self.chunk_read_limit,
        )

        partial_results: list[cudf.DataFrame] = []

        completed_rows = 0

        while reader.has_next():
            table = reader.read_chunk()

            df = cudf.DataFrame.from_pylibcudf(table)

            if progress is not None:
                completed_rows += len(df)
                progress.update(completed_rows)

            partial = self._process_dataframe(
                df,
                english_words,
            )

            if partial is not None and len(partial) > 0:
                partial_results.append(partial)

        if not partial_results:
            return cudf.DataFrame(
                {
                    "word": cudf.Series(
                        [],
                        dtype="object",
                    ),
                    "total_views": cudf.Series(
                        [],
                        dtype="uint64",
                    ),
                }
            )

        return cudf.concat(
            partial_results,
            ignore_index=True,
        )

    @staticmethod
    def _finalize(
        partials: cudf.DataFrame,
        top_k: int,
    ) -> pl.DataFrame:
        """
        Merge intermediate stream reductions and compute the global
        Top-K on the GPU.
        """
        if len(partials) == 0:
            return pl.DataFrame(
                {
                    "word": [],
                    "total_views": [],
                },
                schema={
                    "word": pl.String,
                    "total_views": pl.UInt64,
                },
            )

        final = (
            partials.groupby(
                "word",
                sort=False,
            )["total_views"]
            .sum()
            .reset_index()
            .astype(
                {
                    "total_views": "uint64",
                }
            )
        )

        final = (
            final.sort_values(
                "total_views",
                ascending=False,
            )
            .head(top_k)
            .reset_index(drop=True)
        )

        return pl.DataFrame(final.to_arrow())

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Public entry point for the native GPU query.
        """
        english_words = cudf.DataFrame(
            {
                "word": list(
                    load_english_words(
                        self.english_words_path,
                        self.english_stopwords_path,
                        min_word_length=self.min_word_length,
                    )
                )
            }
        )

        partials = self._process_stream(
            english_words,
            progress=progress,
        )

        return self._finalize(
            partials,
            self.top_k,
        )


def build_query(
    parquet_path: Path,
    english_words_path: Path,
    english_stopwords_path: Path,
    min_word_length: int,
    top_k: int,
    cudf_chunk_read_limit: int,
    **_: object,
) -> GPUCUDFQuery:
    return GPUCUDFQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        top_k=top_k,
        chunk_read_limit=cudf_chunk_read_limit,
    )

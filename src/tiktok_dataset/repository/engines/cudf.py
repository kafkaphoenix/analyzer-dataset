from __future__ import annotations

from pathlib import Path

import cudf
import polars as pl
import pyarrow as pa
import pylibcudf as plc

from tiktok_dataset.domain.data_quality import (
    CORRUPTED_PAYLOAD_PATTERN,
)
from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    BARE_DOMAIN_PATTERN,
    CLEAN_PATTERN_CUDF,
    EMAIL_PATTERN,
    HASHTAG_PATTERN_CUDF,
    MENTION_PATTERN_CUDF,
    URL_SCHEME_PATTERN,
    WORD_PATTERN_CUDF,
)
from tiktok_dataset.repository.vocabulary import (
    load_english_words,
)
from tiktok_dataset.usecase.query import ProgressReporter

ENGINE = "cudf"

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

_CORRUPTED_PAYLOAD_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        CORRUPTED_PAYLOAD_PATTERN,
        _REGEX_DEFAULT_FLAGS,
    )
)

_CLEAN_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        CLEAN_PATTERN_CUDF,
        _REGEX_DEFAULT_FLAGS,
    )
)

_EMAIL_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        EMAIL_PATTERN,
        _REGEX_DEFAULT_FLAGS,
    )
)

_MENTION_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        MENTION_PATTERN_CUDF,
        _REGEX_DEFAULT_FLAGS,
    )
)

_URL_SCHEME_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        URL_SCHEME_PATTERN,
        _REGEX_DEFAULT_FLAGS,
    )
)

_BARE_DOMAIN_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        BARE_DOMAIN_PATTERN,
        _REGEX_DEFAULT_FLAGS,
    )
)

_HASHTAG_PROGRAM = (
    plc.strings.regex_program.RegexProgram.create(
        HASHTAG_PATTERN_CUDF,
        _REGEX_DEFAULT_FLAGS,
    )
)

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

_SCHEME_LITERALS = (
    "http://",
    "https://",
)


def _replace_re(
    series: cudf.Series,
    program: plc.strings.regex_program.RegexProgram,
    replacement: plc.Scalar,
) -> cudf.Series:
    """
    Apply a native libcudf regex replacement while preserving the
    Series index.
    """
    original_index = series.index

    col, meta = series.to_pylibcudf()

    col = plc.strings.replace_re.replace_re(
        col,
        program,
        replacement,
    )

    result = cudf.Series.from_pylibcudf(
        col,
        metadata=meta,
    )
    result.index = original_index

    return result


def _first_literal_position(
    series: cudf.Series,
    literals: tuple[str, ...],
) -> cudf.Series:
    """
    Return the position of the first occurrence of any literal.

    -1 means that none of the literals occurs.
    """
    result = cudf.Series(
        [-1] * len(series),
        index=series.index,
        dtype="int32",
    )

    for literal in literals:
        position = series.str.find(literal)

        result = result.where(
            (position < 0)
            | (
                (result >= 0)
                & (result <= position)
            ),
            position,
        )

    return result


def _build_bare_domain_mask(
    desc: cudf.Series,
) -> cudf.Series:
    """
    Cheap candidate mask for rows containing one of the known bare
    domains.
    """
    result = cudf.Series(
        False,
        index=desc.index,
    )

    for literal in _BARE_DOMAIN_LITERALS:
        result = result | desc.str.contains(
            literal,
            regex=False,
        )

    return result


def _ambiguous_overlap_mask(
    desc: cudf.Series,
    bare_domain_mask: cudf.Series,
) -> cudf.Series:
    """
    Find rows where @/# begins before the earliest URL-like token.

    These rows cannot safely use the normal sequential cleanup because
    the combined regex gives precedence to whichever token starts first.
    """
    marker_mask = (
        desc.str.contains(
            "@",
            regex=False,
        )
        | desc.str.contains(
            "#",
            regex=False,
        )
    )

    url_candidate_mask = (
        bare_domain_mask
        | desc.str.contains(
            "www.",
            regex=False,
        )
        | desc.str.contains(
            "http://",
            regex=False,
        )
        | desc.str.contains(
            "https://",
            regex=False,
        )
    )

    candidate_mask = (
        marker_mask
        & url_candidate_mask
    )

    if not bool(candidate_mask.any()):
        return cudf.Series(
            False,
            index=desc.index,
            dtype="bool",
        )

    candidate = desc.loc[candidate_mask]

    at_position = candidate.str.find("@")
    hash_position = candidate.str.find("#")

    marker_position = at_position.where(
        (at_position >= 0)
        & (
            (hash_position < 0)
            | (at_position < hash_position)
        ),
        hash_position,
    )

    scheme_position = _first_literal_position(
        candidate,
        _SCHEME_LITERALS,
    )

    www_position = candidate.str.find(
        "www.",
    )

    bare_domain_position = _first_literal_position(
        candidate,
        _BARE_DOMAIN_LITERALS,
    )

    # Find the earliest URL-like token.
    url_position = scheme_position

    url_position = url_position.where(
        (www_position < 0)
        | (
            (url_position >= 0)
            & (url_position <= www_position)
        ),
        www_position,
    )

    url_position = url_position.where(
        (bare_domain_position < 0)
        | (
            (url_position >= 0)
            & (url_position <= bare_domain_position)
        ),
        bare_domain_position,
    )

    ambiguous_candidate = (
        (marker_position >= 0)
        & (url_position >= 0)
        & (marker_position < url_position)
    )

    # Reconstruct the full mask without boolean scatter assignment.
    #
    # IMPORTANT:
    # Do not use:
    #
    #     result.loc[candidate.index] = ambiguous_candidate
    #
    # cuDF can produce a size mismatch for that operation.
    #
    # Also do not use a merge here. The candidate result already has
    # the original index, so concat + sort_index is sufficient.
    candidate_result = cudf.Series(
        ambiguous_candidate.values,
        index=candidate.index,
        dtype="bool",
    )

    normal_result = cudf.Series(
        False,
        index=desc.index[~candidate_mask],
        dtype="bool",
    )

    result = cudf.concat(
        [
            normal_result,
            candidate_result,
        ]
    ).sort_index()

    result.index = desc.index

    return result


def _clean_normal_rows(
    desc: cudf.Series,
    bare_domain_mask: cudf.Series,
) -> cudf.Series:
    """
    Fast sequential cleanup for non-ambiguous rows.

    Order:

        URL scheme -> bare domain -> email -> mention -> hashtag
    """
    desc = _replace_re(
        desc,
        _URL_SCHEME_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    normal_bare_domain_mask = bare_domain_mask.loc[
        desc.index
    ]

    if bool(normal_bare_domain_mask.any()):
        subset = desc.loc[
            normal_bare_domain_mask
        ]

        subset = _replace_re(
            subset,
            _BARE_DOMAIN_PROGRAM,
            _REPLACEMENT_SPACE,
        )

        desc = cudf.concat(
            [
                desc.loc[~normal_bare_domain_mask],
                subset,
            ]
        ).sort_index()

    desc = _replace_re(
        desc,
        _EMAIL_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    desc = _replace_re(
        desc,
        _MENTION_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    desc = _replace_re(
        desc,
        _HASHTAG_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    return desc


def clean_desc_cudf(
    desc: cudf.Series,
) -> cudf.Series:
    """
    Clean descriptions using native libcudf regex operations.

    Most rows use the fast sequential pipeline:

        URL -> bare domain -> email -> mention -> hashtag

    Rows where @/# begins before a URL-like token use the combined
    cleanup regex so that leftmost-global regex semantics are preserved.
    """
    original_index = desc.index

    # 1. ASCII lowercase.
    desc = desc.str.translate(
        ASCII_LOWER_MAP,
    )

    # 2. Remove corrupted binary payloads.
    desc = _replace_re(
        desc,
        _CORRUPTED_PAYLOAD_PROGRAM,
        _EMPTY_REPLACEMENT,
    )

    # 3. Build cheap bare-domain candidate mask.
    bare_domain_mask = _build_bare_domain_mask(
        desc,
    )

    # 4. Find rows requiring combined-regex semantics.
    ambiguous_mask = _ambiguous_overlap_mask(
        desc,
        bare_domain_mask,
    )

    if not bool(ambiguous_mask.any()):
        return _clean_normal_rows(
            desc,
            bare_domain_mask,
        )

    # Split using the validated mask.
    ambiguous = desc.loc[
        ambiguous_mask
    ]

    normal = desc.loc[
        ~ambiguous_mask
    ]

    # 5. Correct path for overlapping tokens.
    ambiguous = _replace_re(
        ambiguous,
        _CLEAN_PROGRAM,
        _REPLACEMENT_SPACE,
    )

    # 6. Fast path for everything else.
    normal_bare_domain_mask = bare_domain_mask.loc[
        normal.index
    ]

    normal = _clean_normal_rows(
        normal,
        normal_bare_domain_mask,
    )

    # 7. Recombine without boolean scatter assignment.
    result = cudf.concat(
        [
            normal,
            ambiguous,
        ]
    ).sort_index()

    result.index = original_index

    return result


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
        desc = clean_desc_cudf(
            df["desc"]
        )

        # Extract unique tokens per description.
        words = (
            desc
            .str.findall(
                WORD_PATTERN_CUDF
            )
            .list.unique()
        )

        df = cudf.DataFrame(
            {
                "views": df["views"],
                "word": words,
            }
        )

        # Explode arrays into individual rows.
        df = (
            df
            .explode(
                "word",
                ignore_index=True,
            )
            .dropna(
                subset=["word"]
            )
        )

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
            df
            .groupby(
                "word",
                sort=False,
            )["views"]
            .sum()
            .reset_index(
                name="total_views"
            )
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
        source = plc.io.SourceInfo(
            [
                str(
                    self.parquet_path
                )
            ]
        )

        options = (
            plc.io.parquet.ParquetReaderOptions
            .builder(source)
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

        partial_results: list[
            cudf.DataFrame
        ] = []

        completed_rows = 0

        while reader.has_next():
            table = reader.read_chunk()

            df = cudf.DataFrame.from_pylibcudf(
                table
            )

            if progress is not None:
                completed_rows += len(df)
                progress.update(
                    completed_rows
                )

            partial = self._process_dataframe(
                df,
                english_words,
            )

            if (
                partial is not None
                and len(partial) > 0
            ):
                partial_results.append(
                    partial
                )

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
            partials
            .groupby(
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
            final
            .sort_values(
                "total_views",
                ascending=False,
            )
            .head(
                top_k
            )
            .reset_index(
                drop=True
            )
        )

        return pl.DataFrame(
            final.to_arrow()
        )

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
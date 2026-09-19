from __future__ import annotations

import pytest

from tests.fixtures.case_folding_cases import CASE_FOLDING_CASES
from tests.fixtures.email_cases import EMAIL_CASES
from tests.fixtures.hashtags_cases import HASHTAGS_CASES
from tests.fixtures.mathematical_alphanumeric_cases import MATHEMATICAL_ALPHANUMERIC_CASES
from tests.fixtures.mentions_cases import MENTIONS_CASES
from tests.fixtures.non_latin_cases import NON_LATIN_CASES
from tests.fixtures.simple_ascii_cases import SIMPLE_ASCII_CASES
from tests.fixtures.unicode_symbols_cases import UNICODE_SYMBOLS_CASES
from tests.fixtures.url_cases import URL_CASES
from tests.fixtures.tokenizer_cases import TokenizerCase

TOKENIZER_CASES = (
    *CASE_FOLDING_CASES,
    *EMAIL_CASES,
    *HASHTAGS_CASES,
    *MATHEMATICAL_ALPHANUMERIC_CASES,
    *MENTIONS_CASES,
    *NON_LATIN_CASES,
    *SIMPLE_ASCII_CASES,
    *UNICODE_SYMBOLS_CASES,
    *URL_CASES,
)

@pytest.fixture(
    params=TOKENIZER_CASES,
    ids=lambda case: case.name,
)
def tokenizer_case(request: pytest.FixtureRequest) -> TokenizerCase:
    return request.param

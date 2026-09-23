from __future__ import annotations

import pytest

from tests.scenarios.case_folding_cases import CASE_FOLDING_CASES
from tests.scenarios.email_cases import EMAIL_CASES
from tests.scenarios.hashtags_cases import HASHTAGS_CASES
from tests.scenarios.hashtags_non_latin_cases import HASHTAGS_NON_LATIN_CASES
from tests.scenarios.mathematical_alphanumeric_cases import MATHEMATICAL_ALPHANUMERIC_CASES
from tests.scenarios.mentions_cases import MENTIONS_CASES
from tests.scenarios.simple_ascii_cases import SIMPLE_ASCII_CASES
from tests.scenarios.tokenizer_cases import TokenizerCase
from tests.scenarios.url_cases import URL_CASES

TOKENIZER_CASES = (
    *CASE_FOLDING_CASES,
    *EMAIL_CASES,
    *HASHTAGS_CASES,
    *MATHEMATICAL_ALPHANUMERIC_CASES,
    *MENTIONS_CASES,
    *HASHTAGS_NON_LATIN_CASES,
    *SIMPLE_ASCII_CASES,
    *URL_CASES,
)

@pytest.fixture(
    params=TOKENIZER_CASES,
    ids=lambda case: case.name,
)
def tokenizer_case(request: pytest.FixtureRequest) -> TokenizerCase:
    return request.param

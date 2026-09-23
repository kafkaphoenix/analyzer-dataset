from __future__ import annotations

import pytest

from tiktok_dataset.domain.data_quality import clean_corrupted_desc


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "hello world ����\x01\x1bExifMM*\x08\x05\x01Android TP1A.22",
            "hello world",
        ),
        (
            "@user7321469181527 ����\x01\x1bExifMM*\x08\x05\x01Android TP1A.22",
            "@user7321469181527",
        ),
        (
            "اقتباسات #عبارات #هواجيس ����\x01\x1bExifMM*\x08\x05\x01Android TP1A.22",
            "اقتباسات #عبارات #هواجيس",
        ),
        (
            "normal description",
            "normal description",
        ),
        (
            "",
            "",
        ),
        (
            "hello world ����\x01\x1bExifMM",
            "hello world",
        ),
    ],
)
def test_clean_corrupted_desc(text: str, expected: str) -> None:
    assert clean_corrupted_desc(text) == expected


def test_corrupted_payload_is_removed_even_with_binary_suffix() -> None:
    text = (
        "some valid text ����\x01\x1bExifMM*\x08\x05\x01"
        "JFIF\x00ICC_PROFILE\x00mntrRGB XYZ acsp"
    )

    assert clean_corrupted_desc(text) == "some valid text"


def test_marker_does_not_match_partial_exif_header() -> None:
    text = "hello ExifMM some text"

    assert clean_corrupted_desc(text) == text

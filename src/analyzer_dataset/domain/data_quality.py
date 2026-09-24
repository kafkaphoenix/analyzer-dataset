from __future__ import annotations

CORRUPTED_PAYLOAD_MARKER = "����\x01\x1bExifMM"

# Everything from the known corrupted payload boundary to the end.
CORRUPTED_PAYLOAD_PATTERN = rf"{CORRUPTED_PAYLOAD_MARKER}.*"


def clean_corrupted_desc(desc: str) -> str:
    """Remove known corrupted binary payloads from a description."""
    index = desc.find(CORRUPTED_PAYLOAD_MARKER)
    if index == -1:
        return desc

    return desc[:index]

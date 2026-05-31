from __future__ import annotations


TRUSTED_STATUSES = frozenset(
    {
        "verified",
        "verified_with_rounding",
        "manually_confirmed",
    }
)


def is_trusted_status(status: str) -> bool:
    return status in TRUSTED_STATUSES

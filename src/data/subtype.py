"""Rule-based molecular subtype classification from ER/PR/HER2 IHC.

Standard CAP/NCCN classification simplified for the case where Ki67 is
unavailable (Ki67 normally distinguishes Luminal A vs Luminal B-HER2-).

Mapping:
    HR-, HER2-          -> Triple Negative
    HR-, HER2+          -> HER2-enriched
    HR+, HER2-          -> Luminal A
    HR+, HER2+          -> Luminal B
    anything missing    -> None (Unknown)

Where HR+ = ER+ OR PR+.
"""
from typing import Literal

Subtype = Literal["Luminal A", "Luminal B", "HER2-enriched", "Triple Negative"]


def _normalize(value: str | None) -> bool | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("positive", "pos", "+"):
        return True
    if s in ("negative", "neg", "-"):
        return False
    # "Equivocal", "Indeterminate", "[Not Evaluated]", "", "nan", etc.
    return None


def classify(
    er_status: str | None,
    pr_status: str | None,
    her2_status: str | None,
) -> Subtype | None:
    er = _normalize(er_status)
    pr = _normalize(pr_status)
    her2 = _normalize(her2_status)

    if her2 is None or (er is None and pr is None):
        return None

    hr_positive = bool(er) or bool(pr)

    if not hr_positive and not her2:
        return "Triple Negative"
    if not hr_positive and her2:
        return "HER2-enriched"
    if hr_positive and not her2:
        return "Luminal A"
    if hr_positive and her2:
        return "Luminal B"
    return None

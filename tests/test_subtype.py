"""Molecular subtype classifier — pure unit tests, no DB."""
import pytest

from src.data.subtype import classify


@pytest.mark.parametrize(
    "er,pr,her2,expected",
    [
        ("Positive", "Positive", "Negative", "Luminal A"),
        ("Positive", "Positive", "Positive", "Luminal B"),
        ("Negative", "Negative", "Positive", "HER2-enriched"),
        ("Negative", "Negative", "Negative", "Triple Negative"),
        # HR+ if either ER or PR is positive
        ("Negative", "Positive", "Negative", "Luminal A"),
        ("Positive", "Negative", "Positive", "Luminal B"),
        # Equivocal on a hormone receptor is rescued by the other being +
        ("Equivocal", "Positive", "Negative", "Luminal A"),
    ],
)
def test_subtype_rules(er, pr, her2, expected):
    assert classify(er, pr, her2) == expected


@pytest.mark.parametrize(
    "er,pr,her2",
    [
        (None, None, "Negative"),       # both HR unknown
        ("Positive", "Positive", None),  # HER2 unknown
        ("Equivocal", "Equivocal", "Equivocal"),
        (None, None, None),
    ],
)
def test_unknown_when_required_field_missing(er, pr, her2):
    assert classify(er, pr, her2) is None


def test_case_insensitive_and_symbols():
    assert classify("positive", "NEG", "-") == "Luminal A"
    assert classify("+", "+", "+") == "Luminal B"

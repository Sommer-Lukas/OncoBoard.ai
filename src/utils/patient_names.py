"""Deterministic fake patient names derived from case_id for presentation purposes."""
import hashlib

_FIRST = [
    "Alice", "Barbara", "Carol", "Diana", "Eleanor", "Frances", "Grace",
    "Helen", "Irene", "Joan", "Karen", "Laura", "Margaret", "Nancy",
    "Olivia", "Patricia", "Rachel", "Sandra", "Teresa", "Ursula",
    "Vivian", "Wendy", "Yvonne", "Abigail", "Brenda", "Catherine",
    "Deborah", "Emily", "Fiona", "Gloria", "Hannah", "Ingrid", "Julia",
    "Kathleen", "Linda", "Maria", "Nicole", "Pamela", "Rebecca",
]

_LAST = [
    "Adams", "Baker", "Carter", "Davis", "Evans", "Foster", "Garcia",
    "Harris", "Irving", "Johnson", "King", "Lewis", "Miller", "Nelson",
    "Owen", "Parker", "Quinn", "Roberts", "Smith", "Taylor", "Underwood",
    "Vincent", "Walker", "Xavier", "Young", "Zhang", "Anderson", "Brooks",
    "Collins", "Dixon", "Edwards", "Fleming", "Grant", "Howard", "Ingram",
    "Jenkins", "Knight", "Lambert", "Morgan", "Nash", "Oliver", "Pearce",
]


def fake_name(case_id: str) -> str:
    digest = hashlib.sha256(case_id.encode()).digest()
    first = _FIRST[digest[0] % len(_FIRST)]
    last = _LAST[digest[1] % len(_LAST)]
    return f"{first} {last}"

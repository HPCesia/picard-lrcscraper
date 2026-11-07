from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable, Sequence

from .models import Candidate, Query

_ARTIST_SPLIT_RE = re.compile(
    r"\s*(?:[/&,;+]|\bfeat\.?\b|\bft\.?\b|\bvs\.?\b)\s*", re.IGNORECASE
)
_NON_WORD_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace."""
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = folded.casefold()
    folded = _NON_WORD_RE.sub(" ", folded)
    return _SPACE_RE.sub(" ", folded).strip()


def similarity(left: str, right: str) -> float:
    """Similarity of two strings in the 0..1 range."""
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def artist_similarity(left: str, right: str) -> float:
    """Best similarity across the individual artists of a credit list."""
    if not left.strip() or not right.strip():
        return 0.0
    left_parts = [part for part in _ARTIST_SPLIT_RE.split(left) if part.strip()]
    right_parts = [part for part in _ARTIST_SPLIT_RE.split(right) if part.strip()]
    if not left_parts or not right_parts:
        return similarity(left, right)
    return max(similarity(a, b) for a in left_parts for b in right_parts)


def score_candidate(query: Query, candidate: Candidate) -> float:
    """Rate a hit against the track in the 0..1 range."""
    title = similarity(query.title, candidate.title)
    artist = artist_similarity(query.artist, candidate.artist) if query.artist else 1.0
    score = title * 0.7 + artist * 0.25
    if query.duration and candidate.duration:
        drift = abs(query.duration - candidate.duration)
        score += 0.05 * max(0.0, 1.0 - drift / 15.0)
    else:
        score += 0.02
    return round(score, 4)


def ranked(
    candidates: Iterable[Candidate], query: Query, min_score: float = 0.0
) -> list[Candidate]:
    """Score, filter by `min_score` and return best first."""
    scored = [
        candidate.with_score(score_candidate(query, candidate))
        for candidate in candidates
    ]
    kept = [candidate for candidate in scored if candidate.score >= min_score]
    return sorted(kept, key=lambda candidate: candidate.score, reverse=True)


def best(
    candidates: Sequence[Candidate], query: Query, min_score: float
) -> Candidate | None:
    matches = ranked(candidates, query, min_score)
    return matches[0] if matches else None

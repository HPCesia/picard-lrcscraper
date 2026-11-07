from __future__ import annotations

import re

import pytest


from src.common.models import Candidate, Query
from src.common.scoring import (
    artist_similarity,
    normalize,
    ranked,
    score_candidate,
    similarity,
)


def test_normalize_folds_accents_case_and_punctuation() -> None:
    assert normalize("Beyoncé — Halo (Live!)") == "beyonce halo live"
    assert normalize("  多 空 格  ") == "多 空 格"


def test_similarity_bounds() -> None:
    assert similarity("Bohemian Rhapsody", "bohemian rhapsody") == 1.0
    assert similarity("", "x") == 0.0
    assert 0.5 < similarity("Bohemian Rhapsody", "Bohemian Rapsody") < 1.0


def test_artist_similarity_matches_any_credit() -> None:
    assert artist_similarity("Queen", "Queen & David Bowie") > 0.9
    assert artist_similarity("David Bowie", "Queen feat. David Bowie") > 0.9
    assert artist_similarity("Queen", "Abba") < 0.5


def test_score_rewards_title_artist_and_duration() -> None:
    query = Query(title="Bohemian Rhapsody", artist="Queen", duration=355)
    exact = Candidate("x", "Bohemian Rhapsody", "Queen", duration=355)
    wrong_duration = Candidate("x", "Bohemian Rhapsody", "Queen", duration=120)
    wrong_artist = Candidate("x", "Bohemian Rhapsody", "Some Cover Band")
    assert score_candidate(query, exact) > score_candidate(query, wrong_artist)
    assert score_candidate(query, exact) >= score_candidate(query, wrong_duration)


def test_ranked_filters_and_sorts() -> None:
    query = Query(title="Bohemian Rhapsody", artist="Queen")
    candidates = [
        Candidate("a", "Bohemian Rhapsody", "Queen"),
        Candidate("b", "Unrelated Song", "Nobody"),
        Candidate("c", "Bohemian Rhapsody (Live)", "Queen"),
    ]
    result = ranked(candidates, query, min_score=0.7)
    assert next(item.source for item in result) == "a"
    assert "b" not in [item.source for item in result]
    assert all(item.score >= 0.7 for item in result)


def test_ranked_is_stable_for_equal_scores() -> None:
    query = Query(title="Song", artist="Artist")
    candidates = [
        Candidate("one", "Song", "Artist"),
        Candidate("two", "Song", "Artist"),
    ]
    first = ranked(candidates, query)
    second = ranked(list(reversed(candidates)), query)
    assert {item.source for item in first} == {item.source for item in second}


@pytest.mark.parametrize("text", ["AC/DC", "Ke$ha", "!!!", "Sigur Rós"])
def test_normalize_never_raises(text: str) -> None:
    assert isinstance(re.sub(r"\s+", " ", normalize(text)), str)

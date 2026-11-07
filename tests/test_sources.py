from __future__ import annotations

import base64
import json


from src.common.models import Candidate, Query, SessionOptions
from src.sources.kugou import (
    KugouSession,
    build_search_queryargs,
    parse_search,
    sign,
)
from src.sources.kuwo import KuwoSession, KuwoSource, parse_loose_json
from src.sources.lrclib import (
    LrclibSession,
    LrclibSource,
    parse_search as lrclib_search,
)
from src.sources.lyricsovh import LyricsOvhSource
from src.sources.netease import (
    NeteaseSource,
    parse_lyric,
    parse_search as netease_search,
)

OPTIONS = SessionOptions()


def test_registry_metadata() -> None:
    assert LrclibSource.ID == "lrclib"
    assert NeteaseSource.REQUIRES_ARTIST is False
    assert LyricsOvhSource.REQUIRES_ARTIST is True


def test_lrclib_search_filters_instrumentals_and_empty_entries() -> None:
    payload = [
        {
            "trackName": "Bohemian Rhapsody",
            "artistName": "Queen",
            "albumName": "A Night at the Opera",
            "duration": 354.0,
            "instrumental": False,
            "plainLyrics": "plain",
            "syncedLyrics": "[00:01.00] synced",
        },
        {"trackName": "Untitled", "instrumental": True},
        {"trackName": "Empty", "instrumental": False},
    ]
    candidates = lrclib_search(payload)
    assert len(candidates) == 1
    assert candidates[0].duration == 354
    assert candidates[0].payload["synced"].startswith("[00:01.00]")


def test_lrclib_prefers_synced_lyrics() -> None:
    candidate = Candidate(
        "lrclib",
        "Song",
        payload={"plain": "plain text", "synced": "[00:01.00] synced"},
    )
    session = LrclibSession(Query("Song"), SessionOptions(prefer_synced=True))
    lyric = session.begin_fetch(candidate)
    assert lyric is not None and lyric.synced


def test_lrclib_can_prefer_plain_lyrics() -> None:
    candidate = Candidate(
        "lrclib",
        "Song",
        payload={"plain": "plain text", "synced": "[00:01.00] synced"},
    )
    session = LrclibSession(Query("Song"), SessionOptions(prefer_synced=False))
    lyric = session.begin_fetch(candidate)
    assert lyric is not None and not lyric.synced and lyric.text == "plain text"


def test_lrclib_returns_none_without_lyrics() -> None:
    session = LrclibSession(Query("Song"), OPTIONS)
    assert session.begin_fetch(Candidate("lrclib", "Song", payload={})) is None


def test_netease_search_parses_songs() -> None:
    payload = {
        "result": {
            "songs": [
                {
                    "id": 1868553,
                    "name": "Bohemian Rhapsody",
                    "duration": 355195,
                    "artists": [{"name": "Queen"}],
                    "album": {"name": "A Night at the Opera"},
                }
            ]
        }
    }
    candidates = netease_search(payload)
    assert candidates[0].payload == {"id": 1868553}
    assert candidates[0].artist == "Queen"
    assert candidates[0].duration == 355


def test_netease_lyric_parsing() -> None:
    response = {"lrc": {"lyric": "[00:01.00] 作词 : Freddie\n[00:02.00]Hello"}}
    lyric = parse_lyric(response, Candidate("netease", "Song"))
    assert lyric is not None
    assert lyric.text == "[00:02.00]Hello"
    assert lyric.synced


def test_netease_lyric_rejects_empty_payload() -> None:
    assert (
        parse_lyric({"lrc": {"lyric": "纯音乐，请欣赏"}}, Candidate("netease", "Song"))
        is None
    )
    assert parse_lyric({}, Candidate("netease", "Song")) is None


def test_netease_lyric_carries_translation() -> None:
    response = {
        "lrc": {"lyric": "[00:02.00]Hello\n[00:04.00]World"},
        "tlyric": {"lyric": "[00:02.00]你好\n[00:04.00]世界"},
    }
    lyric = parse_lyric(response, Candidate("netease", "Song"))
    assert lyric is not None
    assert lyric.translation == "[00:02.00]你好\n[00:04.00]世界"


def test_netease_ignores_untimed_or_missing_translation() -> None:
    untimed = {
        "lrc": {"lyric": "[00:02.00]Hello"},
        "tlyric": {"lyric": "你好"},
    }
    assert parse_lyric(untimed, Candidate("netease", "Song")).translation == ""
    plain = {"lrc": {"lyric": "[00:02.00]Hello"}}
    assert parse_lyric(plain, Candidate("netease", "Song")).translation == ""


def test_kugou_signature_is_stable_and_uses_secret() -> None:
    assert sign("abc") == sign("abc")
    assert sign("abc") != sign("abd")


def test_kugou_search_queryargs_contains_signature() -> None:
    args = build_search_queryargs("bohemian rhapsody", "1700000000000")
    assert args["signature"] == sign(
        "bitrate=0clienttime=1700000000000clientver=2000dfid=-inputtype=0iscorrection=1"
        "isfuzzy=0keyword=bohemian rhapsodymid=1700000000000page=1pagesize=10"
        "platform=WebFilterprivilege_filter=0srcappid=2919tag=emuserid=-1uuid=1700000000000"
    )
    assert args["keyword"] == "bohemian rhapsody"


def test_kugou_search_strips_highlight_markup() -> None:
    payload = {
        "data": {
            "lists": [
                {
                    "SongName": "<em>Bohemian</em> Rhapsody",
                    "SingerName": "Queen、David Bowie",
                    "AlbumName": "Album",
                    "FileHash": "A38CC900",
                    "Duration": 354,
                }
            ]
        }
    }
    candidates = parse_search(payload)
    assert candidates[0].title == "Bohemian Rhapsody"
    assert candidates[0].artist == "Queen, David Bowie"
    assert candidates[0].payload["hash"] == "A38CC900"


def test_kugou_download_decodes_base64_lrc() -> None:
    raw = "\ufeff[ar:Queen]\n[00:01.00] Hello\n[00:02.00] World"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    session = KugouSession(Query("Song"), OPTIONS)
    candidate = Candidate("kugou", "Song", payload={"hash": "H"})
    session.begin_fetch(candidate)
    step = session.handle_fetch(
        {"candidates": [{"id": "1", "accesskey": "k"}]}, candidate
    )
    assert step is not None
    lyric = session.handle_fetch({"content": encoded}, candidate)
    assert lyric is not None
    assert lyric.text == "[ar:Queen]\n[00:01.00] Hello\n[00:02.00] World"


def test_kugou_without_candidates_returns_none() -> None:
    session = KugouSession(Query("Song"), OPTIONS)
    candidate = Candidate("kugou", "Song", payload={"hash": "H"})
    session.begin_fetch(candidate)
    assert session.handle_fetch({"candidates": []}, candidate) is None


def test_kuwo_parses_single_quoted_payload() -> None:
    text = "{'abslist':[{'SONGNAME':'Bohemian&nbsp;Rhapsody','ARTIST':'Queen','ALBUM':'','DURATION':'354','MUSICRID':'MUSIC_123'}],'TOTAL':'1'}"
    data = parse_loose_json(text)
    assert data["abslist"][0]["MUSICRID"] == "MUSIC_123"
    session = KuwoSession(Query("Song"), OPTIONS)
    candidates = session.handle_search(text)
    assert candidates[0].title == "Bohemian Rhapsody"
    assert candidates[0].payload["rid"] == "123"


def test_kuwo_lyric_builds_lrc_from_lines() -> None:
    payload = json.dumps(
        {
            "data": {
                "lrclist": [
                    {"lineLyric": "以下歌词翻译由文曲大模型提供", "time": "0.0"},
                    {"lineLyric": "Hello", "time": "61.5"},
                ]
            }
        }
    )
    session = KuwoSession(Query("Song"), OPTIONS)
    lyric = session.handle_fetch(payload, Candidate("kuwo", "Song"))
    assert lyric is not None
    assert lyric.text == "[01:01.50]Hello"
    assert lyric.synced


def test_kuwo_empty_response_returns_none() -> None:
    session = KuwoSession(Query("Song"), OPTIONS)
    assert session.handle_fetch("not json at all", Candidate("kuwo", "Song")) is None


def test_kuwo_source_id() -> None:
    assert KuwoSource.ID == "kuwo"
    assert KuwoSource().supports(Query("Song"))


def test_lyricsovh_needs_artist() -> None:
    source = LyricsOvhSource()
    assert not source.supports(Query("Song"))
    assert source.supports(Query("Song", "Artist"))


def test_lyricsovh_fetch_url_is_quoted() -> None:
    session = LyricsOvhSource().session(Query("A Song", "An Artist"), OPTIONS)
    candidates = session.begin_search()
    assert candidates
    request = session.begin_fetch(candidates[0])
    assert request.url == "https://api.lyrics.ovh/v1/An%20Artist/A%20Song"

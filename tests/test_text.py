from __future__ import annotations

from src.common.text import (
    clean_lyrics,
    format_duration,
    is_synced,
    lrc_timestamp,
    merge_bilingual,
    parse_duration,
    sidecar_base,
    sidecar_path,
)


def test_is_synced_detects_lrc_tags() -> None:
    assert is_synced("[00:12.34] hello")
    assert is_synced("[1:02:03] hello")
    assert not is_synced("just a line")


def test_clean_lyrics_drops_credits_and_notices() -> None:
    raw = (
        "[id:$00000001]\n"
        "[ar:Queen]\n"
        "[00:00.000] 作词 : Freddie Mercury\n"
        "[00:01.000] 作曲 : Freddie Mercury\n"
        "[00:02.000] 以下歌词翻译由文曲大模型提供\n"
        "[00:03.000] Is this the real life?\n"
        "[00:04.000] \n"
        "\n"
        "[00:05.000] Any way the wind blows"
    )
    assert clean_lyrics(raw) == (
        "[ar:Queen]\n"
        "[00:03.000] Is this the real life?\n"
        "\n"
        "[00:05.000] Any way the wind blows"
    )


def test_clean_lyrics_normalises_line_endings_and_bom() -> None:
    assert clean_lyrics("\ufeffone\r\ntwo\r\n\r\n\r\nthree") == "one\ntwo\n\nthree"


def test_clean_lyrics_keeps_english_credits_out() -> None:
    raw = "[00:00.00]Lyrics: Somebody\n[00:02.00]Produced by Somebody\n[00:04.00]real line"
    assert clean_lyrics(raw) == "[00:04.00]real line"


def test_clean_lyrics_returns_empty_for_noise_only() -> None:
    assert clean_lyrics("纯音乐，请欣赏") == ""
    assert clean_lyrics("") == ""


def test_parse_duration() -> None:
    assert parse_duration("3:55") == 235
    assert parse_duration("1:02:03") == 3723
    assert parse_duration("nonsense") is None
    assert parse_duration("") is None


def test_format_duration() -> None:
    assert format_duration(235) == "3:55"
    assert format_duration(3723) == "1:02:03"
    assert format_duration(None) == ""


def test_lrc_timestamp() -> None:
    assert lrc_timestamp(0) == "[00:00.00]"
    assert lrc_timestamp(83.5) == "[01:23.50]"
    assert lrc_timestamp(-5) == "[00:00.00]"


def test_sidecar_paths() -> None:
    assert sidecar_base("/music/Queen/a.flac") == "/music/Queen/a"
    assert sidecar_path("/music/Queen/a.flac", ".lrc") == "/music/Queen/a.lrc"
    assert sidecar_path("/music/Queen/a.b.flac", ".txt") == "/music/Queen/a.b.txt"


def test_credit_heuristic_drops_role_labels() -> None:
    raw = (
        "[00:00.00]录音工程：杨瑞代（Alfa Studio）\n"
        "[00:01.00]合声编写：周杰伦\n"
        "[00:02.00]Lyrics: Someone\n"
        "[00:03.00]Mixed by Bob\n"
        "[00:04.00]真实歌词"
    )
    assert clean_lyrics(raw) == "[00:04.00]真实歌词"


def test_credit_heuristic_keeps_dialogue_lines() -> None:
    assert clean_lyrics("[00:01.00]他说：我不去") == "[00:01.00]他说：我不去"
    assert clean_lyrics("[00:01.00]Time: 4:00") == "[00:01.00]Time: 4:00"


def test_merge_bilingual_stacks_translation_under_each_line() -> None:
    original = "[ar:Artist]\n[00:01.00]Hello\n[00:03.00]World"
    translation = "[00:01.00]你好\n[00:03.00]世界"
    assert merge_bilingual(original, translation) == (
        "[ar:Artist]\n"
        "[00:01.00]Hello\n[00:01.00]你好\n"
        "[00:03.00]World\n[00:03.00]世界"
    )


def test_merge_bilingual_tolerates_small_drift() -> None:
    assert merge_bilingual("[00:01.00]Hello", "[00:01.20]你好") == (
        "[00:01.00]Hello\n[00:01.00]你好"
    )


def test_merge_bilingual_drops_translations_without_a_match() -> None:
    merged = merge_bilingual(
        "[00:01.00]Hello\n[00:05.00]Bye",
        "[00:01.00]你好\n[00:09.00]再见",
    )
    assert merged == "[00:01.00]Hello\n[00:01.00]你好\n[00:05.00]Bye"


def test_merge_bilingual_returns_original_without_timed_translation() -> None:
    original = "[00:01.00]Hello"
    assert merge_bilingual(original, "") == original
    assert merge_bilingual(original, "no time tags here") == original


def test_merge_bilingual_repeats_translation_for_each_time_tag() -> None:
    merged = merge_bilingual(
        "[00:01.00][00:10.00]Hello",
        "[00:01.00]你好\n[00:10.00]你好",
    )
    assert merged == "[00:01.00][00:10.00]Hello\n[00:01.00]你好\n[00:10.00]你好"

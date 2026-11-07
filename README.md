# LRC Scraper

A [MusicBrainz Picard](https://picard.musicbrainz.org/) 3.0 plugin that fetches
lyrics from several providers. Lyrics go into the `lyrics` tag and, optionally,
into a `.lrc` (or `.txt`) sidecar next to the audio file.

Sources are queried in the order you configure, and the first acceptable match
wins. A provider that has the song but no lyrics for it is skipped, and the next
one is asked instead.

## Requirements

Picard 3.0 or newer. The plugin uses the plugin3 API and needs nothing beyond
what Picard ships.

## Sources

| Source | Search | Synced lyrics | Notes |
| --- | --- | --- | --- |
| [LRCLIB](https://lrclib.net) | title, plus artist when known | yes | crowd-sourced, strongest for Western releases |
| [NetEase Cloud Music](https://music.163.com) | keyword | yes | strongest for Chinese releases, often ships translations |
| [Kugou](https://www.kugou.com) | keyword | yes | Chinese releases |
| [Kuwo](https://www.kuwo.cn) | keyword | yes | Chinese releases, often has the song without lyrics |
| [Lyrics.ovh](https://lyrics.ovh) | artist and title | no | plain text only, skipped when the track has no artist |

"Synced" means the provider can return timestamps. Whether a given track gets
them depends on what the provider stores for that row.

All five are unofficial web APIs, so they can change or start rate limiting
without notice.

## Installation

- **Git URL:** `Options` → `Plugins` → **Install Plugin…** → `URL` tab → paste
  this repository URL.
- **Local folder:** `Options` → `Plugins` → **Install Plugin…** → `Local` tab →
  pick this checkout, the folder holding `MANIFEST.toml`.
- **CLI:** `picard-cli plugins install <url-or-path>`

## Usage

### Settings

`Options` → `Plugins` → `LRC Scraper`

- **Source priority:** every provider is listed with a checkbox. Checked sources
  are queried top to bottom. Use *Move Up*/*Move Down* or drag to reorder, and
  *Restore Defaults* to go back to the shipped order. Uncheck a source to skip
  it.
- **Fetch lyrics when a track is loaded:** scrape as soon as a file is added to
  a track. Existing lyrics are kept.
- **Fetch lyrics when a file is saved:** fill in lyrics missing at save time,
  then save the file again so the new tag reaches the file. Existing lyrics are
  kept.
- **Prefer synchronized lyrics:** take the timed version when a provider has both.
- **Merge translations under the lyrics:** write a bilingual lyric, each
  translated line under the original it translates. Off by default. Only NetEase
  returns translations, and only for timed lyrics.
- **Write a lyric sidecar file:** write `<track>.lrc` next to the audio file.
- **Save plain lyrics as .txt:** use `.txt` for lyrics without timestamps. Timed
  lyrics always go to `.lrc`.
- **When lyrics already exist:** `Never`, `Ask me` or `Always`. Only the context
  menu's *Fetch lyrics from configured sources* consults this. Loading and saving
  never overwrite, and picking a result from the manual search always writes.
- **Minimum match score:** 0..1, default 0.6. Hits scoring lower are dropped
  before anything is fetched. Title similarity carries most of the score, with
  artist and track length added on top. Raise it when the wrong lyrics keep
  winning, lower it when good hits get rejected.

### Context menu

Right click a track or an album:

- **Fetch lyrics from configured sources:** the automatic scrape.
- **Search lyrics and pick a result…:** search every enabled source, then pick
  from the matches ranked best first and filtered by the minimum score. Nothing
  is written until you pick a row. Picking writes that lyric whatever the
  overwrite setting says.

## Behaviour notes

- The tag and the sidecar carry the same text, UTF-8 with LF line endings. A
  sidecar replaces any file of that name next to the track.
- A sidecar that cannot be written is logged as a warning and the tag is set
  anyway, so a read-only folder still gets lyrics.
- Credit lines (`作词 : …`, `Produced by …`), provider notices and stray
  `[id:…]`/`[by:…]` tags are stripped. The lyric text itself is left alone.
- With translations merged, each translated line reuses the original's
  timestamp, so players that stack equal timestamps show both rows. A translation
  landing more than 0.3 seconds from any original line is dropped.
- Up to three hits per provider, highest ranked first, are tried before the next
  provider is consulted.
- Instrumental tracks, empty responses and unreadable responses all fall through
  to the next source.
- Scraping during track load is a blocking album task, which Picard caps at 30
  seconds. A source that stays slow is better disabled.
- Every source query and every failure is logged at debug level. Picard's
  `View Error/Debug Log` (Ctrl+G) shows them.

## Troubleshooting

- **Good match rejected:** the score sits below the threshold. Lower *Minimum
  match score* by 0.05 and retry.
- **Wrong lyrics picked:** raise the threshold, or move a stronger source up.
- **Lyrics appear in Picard but not in other players:** the tag is only in
  Picard's memory until the file is saved. Enable *Fetch lyrics when a file is
  saved*, or save the album.
- **Loading got slow:** disable *Fetch lyrics when a track is loaded* or the slow
  sources.

## Development

```bash
pytest          # unit tests
ruff check      # lint
```

`src/common`, `src/sources` and `src/services/runner.py` import no Picard
modules, so their tests run without Picard or PyQt6. `tests/test_scrape.py`
skips itself when Picard or PyQt6 is missing. Everything else is glue to the
Picard API:

| Path | Contents |
| --- | --- |
| `__init__.py` | entry point: registers the options page, both actions and both hooks |
| `src/common` | models, lyric cleanup, scoring |
| `src/sources` | one module per provider, plus `registry.py` for the order |
| `src/services` | `runner.py` drives the provider state machines, `scrape.py` holds the Picard-facing flow, `apply.py` writes tags and sidecars, `web.py` adapts `api.web_service` |
| `src/options`, `src/ui` | Qt options page and dialogs |
| `src/actions`, `src/callbacks` | Picard track/album actions and post-addition/post-save processors |

### Adding a source

1. Add `src/sources/<name>.py` with a `Source` subclass. Set `ID`, `NAME`, and
   `REQUIRES_ARTIST` when the provider needs an artist. `session()` returns a
   `Session`.
2. Each `begin_search`/`handle_search`/`begin_fetch`/`handle_fetch` step returns
   a `Request`, a list of `Candidate`s, or a `Lyric`. The matching `handle_*`
   receives the response. Requests are sent by `runner.py`, which fakes the
   transport in tests.
3. Add the class to `SOURCES` in `src/sources/registry.py`. IDs missing from a
   saved order are appended, so existing sources keep their place.
4. Add parse tests in `tests/test_sources.py` using recorded responses.

## Acknowledgements

- <https://github.com/izaz4141/picard-lrclib>
- <https://github.com/xhongc/music-tag-web>

## License

GPL-3.0-or-later. Lyrics come from third-party services, so keep their use
personal.

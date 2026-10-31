"""Tests for the Discover placeholder folders on disk."""

from pathlib import Path
from xml.etree import ElementTree

import pytest
from medialab_contracts import (
    DISCOVER_CLIP_FILENAME,
    DISCOVER_CLIP_SUBDIR,
    MEDIA_TYPE_SUBDIRS,
    MediaType,
    PlaceholderState,
)

from medialab_jellyfin.services import placeholders

TMDB_ID = 238
TITLE = "The Godfather"
YEAR = 1972


def _write(
    root: Path,
    media_type: MediaType = MediaType.MOVIE,
    state: PlaceholderState = PlaceholderState.AVAILABLE,
    title: str = TITLE,
    year: int | None = YEAR,
) -> bool:
    return placeholders.write_placeholder(
        root, media_type=media_type, tmdb_id=TMDB_ID, title=title, year=year, state=state
    )


def _folder(root: Path, media_type: MediaType = MediaType.MOVIE) -> Path:
    folders = list((root / MEDIA_TYPE_SUBDIRS[media_type]).iterdir())
    assert len(folders) == 1
    return folders[0]


def _nfo(folder: Path, media_type: MediaType = MediaType.MOVIE) -> ElementTree.Element:
    return ElementTree.parse(folder / placeholders.NFO_FILENAMES[media_type]).getroot()


class TestWriteMovie:
    def test_creates_the_folder_named_with_the_tmdb_tag(self, tmp_path: Path) -> None:
        assert _write(tmp_path) is True
        assert _folder(tmp_path).name == f"{TITLE} ({YEAR}) [tmdbid-{TMDB_ID}]"

    def test_nfo_carries_title_year_and_tmdb_id(self, tmp_path: Path) -> None:
        _write(tmp_path)
        nfo = _nfo(_folder(tmp_path))
        assert nfo.tag == "movie"
        assert nfo.findtext("title") == TITLE
        assert nfo.findtext("year") == str(YEAR)
        assert nfo.findtext("tmdbid") == str(TMDB_ID)
        uniqueid = nfo.find("uniqueid")
        assert uniqueid is not None
        assert uniqueid.get("type") == "tmdb"
        assert uniqueid.text == str(TMDB_ID)

    def test_copies_the_clip_as_the_movie_file(self, tmp_path: Path) -> None:
        _write(tmp_path)
        video = _folder(tmp_path) / f"{TITLE} ({YEAR}).mp4"
        clip = tmp_path / DISCOVER_CLIP_SUBDIR / DISCOVER_CLIP_FILENAME
        assert video.read_bytes() == clip.read_bytes()
        assert video.stat().st_size > 0

    def test_state_suffix_goes_into_the_title(self, tmp_path: Path) -> None:
        _write(tmp_path, state=PlaceholderState.REQUESTED)
        assert _nfo(_folder(tmp_path)).findtext("title") == f"{TITLE} - Requested"

    def test_no_year_omits_it_from_names(self, tmp_path: Path) -> None:
        _write(tmp_path, year=None)
        folder = _folder(tmp_path)
        assert folder.name == f"{TITLE} [tmdbid-{TMDB_ID}]"
        assert (folder / f"{TITLE}.mp4").exists()
        assert _nfo(folder).find("year") is None

    def test_unsafe_characters_are_stripped_from_names(self, tmp_path: Path) -> None:
        _write(tmp_path, title='Mission: Impossible / "Ghost" Protocol?')
        folder = _folder(tmp_path)
        assert folder.name == f"Mission Impossible Ghost Protocol ({YEAR}) [tmdbid-{TMDB_ID}]"
        assert _nfo(folder).findtext("title") == 'Mission: Impossible / "Ghost" Protocol?'


class TestWriteShow:
    def test_creates_tvshow_nfo_and_one_stub_episode(self, tmp_path: Path) -> None:
        _write(tmp_path, media_type=MediaType.SHOW, title="Severance", year=2022)
        folder = _folder(tmp_path, MediaType.SHOW)
        assert _nfo(folder, MediaType.SHOW).tag == "tvshow"
        assert (folder / "Season 01" / "Severance S01E01.mp4").exists()


class TestRewrite:
    def test_unchanged_write_reports_no_change(self, tmp_path: Path) -> None:
        _write(tmp_path)
        assert _write(tmp_path) is False

    def test_state_change_rewrites_the_nfo_in_place(self, tmp_path: Path) -> None:
        _write(tmp_path)
        assert _write(tmp_path, state=PlaceholderState.DOWNLOADING) is True
        assert _nfo(_folder(tmp_path)).findtext("title") == f"{TITLE} - Downloading"

    def test_title_change_keeps_the_existing_folder(self, tmp_path: Path) -> None:
        _write(tmp_path)
        _write(tmp_path, title="Il Padrino")
        folder = _folder(tmp_path)
        assert folder.name.startswith(TITLE)
        assert _nfo(folder).findtext("title") == "Il Padrino"


class TestRemove:
    def test_removes_the_folder(self, tmp_path: Path) -> None:
        _write(tmp_path)
        assert placeholders.remove_placeholder(tmp_path, MediaType.MOVIE, TMDB_ID) is True
        assert not list((tmp_path / MEDIA_TYPE_SUBDIRS[MediaType.MOVIE]).iterdir())

    def test_absent_is_a_no_op(self, tmp_path: Path) -> None:
        assert placeholders.remove_placeholder(tmp_path, MediaType.MOVIE, TMDB_ID) is False

    def test_leaves_other_placeholders(self, tmp_path: Path) -> None:
        _write(tmp_path)
        placeholders.write_placeholder(
            tmp_path,
            media_type=MediaType.MOVIE,
            tmdb_id=949,
            title="Heat",
            year=1995,
            state=PlaceholderState.AVAILABLE,
        )
        placeholders.remove_placeholder(tmp_path, MediaType.MOVIE, TMDB_ID)
        assert [f.name for f in (tmp_path / "Movies").iterdir()] == ["Heat (1995) [tmdbid-949]"]


class TestList:
    def test_lists_tmdb_id_title_and_state(self, tmp_path: Path) -> None:
        _write(tmp_path, state=PlaceholderState.NOT_FOUND)
        [info] = placeholders.list_placeholders(tmp_path, MediaType.MOVIE)
        assert (info.tmdb_id, info.title, info.state) == (
            TMDB_ID,
            TITLE,
            PlaceholderState.NOT_FOUND,
        )

    def test_missing_type_dir_is_empty(self, tmp_path: Path) -> None:
        assert placeholders.list_placeholders(tmp_path, MediaType.SHOW) == []

    def test_foreign_folders_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "Movies" / "Random folder").mkdir(parents=True)
        assert placeholders.list_placeholders(tmp_path, MediaType.MOVIE) == []


class TestClip:
    def test_existing_clip_is_not_overwritten(self, tmp_path: Path) -> None:
        custom = tmp_path / DISCOVER_CLIP_SUBDIR / DISCOVER_CLIP_FILENAME
        custom.parent.mkdir()
        custom.write_bytes(b"custom clip")
        _write(tmp_path)
        assert (_folder(tmp_path) / f"{TITLE} ({YEAR}).mp4").read_bytes() == b"custom clip"


@pytest.mark.parametrize("media_type", list(MediaType))
def test_every_media_type_has_an_nfo_name(media_type: MediaType) -> None:
    assert placeholders.NFO_FILENAMES[media_type].endswith(".nfo")

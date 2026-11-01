"""Discover placeholder folders on disk: one folder per title with an .nfo that
Jellyfin matches by TMDB id and a copy of the request clip as its playable file."""

import re
import shutil
from importlib import resources
from pathlib import Path
from xml.etree import ElementTree

from medialab_contracts import (
    DISCOVER_CLIP_FILENAME,
    DISCOVER_CLIP_SUBDIR,
    MEDIA_TYPE_SUBDIRS,
    MediaType,
    PlaceholderInfo,
    PlaceholderState,
    placeholder_title,
)

NFO_FILENAMES: dict[MediaType, str] = {
    MediaType.MOVIE: "movie.nfo",
    MediaType.SHOW: "tvshow.nfo",
}
_NFO_ROOT_TAGS: dict[MediaType, str] = {
    MediaType.MOVIE: "movie",
    MediaType.SHOW: "tvshow",
}
_STUB_SEASON_DIR = "Season 01"
_STUB_EPISODE_TAG = "S01E01"
_VIDEO_SUFFIX = ".mp4"
_TMDB_TAG_TEMPLATE = "[tmdbid-{tmdb_id}]"
_PROVIDER_TMDB = "tmdb"
_ASSET_PACKAGE = "medialab_jellyfin.assets"
_NFO_ENCODING = "utf-8"

# Elements Jellyfin reads, plus two of ours it ignores: the bare title and the
# state, so listing never has to parse the suffix back out of the display title.
_TAG_TITLE = "title"
_TAG_YEAR = "year"
_TAG_TMDBID = "tmdbid"
_TAG_UNIQUEID = "uniqueid"
_TAG_BASE_TITLE = "medialab_title"
_TAG_STATE = "medialab_state"

_UNSAFE_NAME_CHARS = re.compile(r'[<>:"/\\|?*]')
_SPACES = re.compile(r"\s+")


def _safe_name(title: str) -> str:
    return _SPACES.sub(" ", _UNSAFE_NAME_CHARS.sub(" ", title)).strip()


def _base_name(title: str, year: int | None) -> str:
    name = _safe_name(title)
    return f"{name} ({year})" if year is not None else name


def _type_dir(root: Path, media_type: MediaType) -> Path:
    return root / MEDIA_TYPE_SUBDIRS[media_type]


def _find_folder(root: Path, media_type: MediaType, tmdb_id: int) -> Path | None:
    type_dir = _type_dir(root, media_type)
    if not type_dir.is_dir():
        return None
    tag = _TMDB_TAG_TEMPLATE.format(tmdb_id=tmdb_id)
    return next((d for d in type_dir.iterdir() if d.is_dir() and d.name.endswith(tag)), None)


def ensure_clip(root: Path) -> Path:
    """The clip every placeholder copies. Written from the bundled asset only
    when absent, so a custom clip dropped in its place is kept."""
    clip = root / DISCOVER_CLIP_SUBDIR / DISCOVER_CLIP_FILENAME
    if not clip.exists():
        clip.parent.mkdir(parents=True, exist_ok=True)
        asset = resources.files(_ASSET_PACKAGE).joinpath(DISCOVER_CLIP_FILENAME)
        clip.write_bytes(asset.read_bytes())
    return clip


def _nfo_bytes(
    media_type: MediaType, tmdb_id: int, title: str, year: int | None, state: PlaceholderState
) -> bytes:
    root = ElementTree.Element(_NFO_ROOT_TAGS[media_type])
    ElementTree.SubElement(root, _TAG_TITLE).text = placeholder_title(title, state)
    if year is not None:
        ElementTree.SubElement(root, _TAG_YEAR).text = str(year)
    ElementTree.SubElement(root, _TAG_TMDBID).text = str(tmdb_id)
    uniqueid = ElementTree.SubElement(
        root, _TAG_UNIQUEID, {"type": _PROVIDER_TMDB, "default": "true"}
    )
    uniqueid.text = str(tmdb_id)
    ElementTree.SubElement(root, _TAG_BASE_TITLE).text = title
    ElementTree.SubElement(root, _TAG_STATE).text = state.value
    ElementTree.indent(root)
    return ElementTree.tostring(root, encoding=_NFO_ENCODING, xml_declaration=True)


def _video_path(folder: Path, media_type: MediaType, title: str, year: int | None) -> Path:
    if media_type is MediaType.SHOW:
        stub = f"{_safe_name(title)} {_STUB_EPISODE_TAG}{_VIDEO_SUFFIX}"
        return folder / _STUB_SEASON_DIR / stub
    return folder / f"{_base_name(title, year)}{_VIDEO_SUFFIX}"


def write_placeholder(
    root: Path,
    *,
    media_type: MediaType,
    tmdb_id: int,
    title: str,
    year: int | None,
    state: PlaceholderState,
) -> bool:
    """Create the placeholder, or rewrite its .nfo when title, year or state
    changed. An existing folder keeps its name. True when anything was written."""
    nfo = _nfo_bytes(media_type, tmdb_id, title, year, state)
    folder = _find_folder(root, media_type, tmdb_id)
    if folder is not None:
        nfo_path = folder / NFO_FILENAMES[media_type]
        if nfo_path.exists() and nfo_path.read_bytes() == nfo:
            return False
        nfo_path.write_bytes(nfo)
        return True

    tag = _TMDB_TAG_TEMPLATE.format(tmdb_id=tmdb_id)
    folder = _type_dir(root, media_type) / f"{_base_name(title, year)} {tag}"
    video = _video_path(folder, media_type, title, year)
    video.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ensure_clip(root), video)
    (folder / NFO_FILENAMES[media_type]).write_bytes(nfo)
    return True


def remove_placeholder(root: Path, media_type: MediaType, tmdb_id: int) -> bool:
    """Delete the placeholder folder. True when one existed."""
    folder = _find_folder(root, media_type, tmdb_id)
    if folder is None:
        return False
    shutil.rmtree(folder)
    return True


def _read(folder: Path, media_type: MediaType) -> PlaceholderInfo | None:
    nfo_path = folder / NFO_FILENAMES[media_type]
    if not nfo_path.is_file():
        return None
    try:
        nfo = ElementTree.parse(nfo_path).getroot()
        tmdb_id = int(nfo.findtext(_TAG_TMDBID) or "")
        state = PlaceholderState(nfo.findtext(_TAG_STATE))
    except (ElementTree.ParseError, ValueError):
        return None
    title = nfo.findtext(_TAG_BASE_TITLE) or nfo.findtext(_TAG_TITLE) or ""
    return PlaceholderInfo(tmdb_id=tmdb_id, title=title, state=state)


def list_placeholders(root: Path, media_type: MediaType) -> list[PlaceholderInfo]:
    """Every readable placeholder of one type, by folder name order. Folders
    without a medialab .nfo are not placeholders and are skipped."""
    type_dir = _type_dir(root, media_type)
    if not type_dir.is_dir():
        return []
    found = (_read(d, media_type) for d in sorted(type_dir.iterdir()) if d.is_dir())
    return [info for info in found if info is not None]

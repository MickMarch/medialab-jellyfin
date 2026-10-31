"""Request and response schemas for the Discover placeholder and favorites endpoints."""

from enum import Enum

from medialab_contracts import MediaType, PlaceholderState
from pydantic import BaseModel, field_validator


class FavoriteScope(str, Enum):
    DISCOVER = "discover"
    """Favorites on placeholders: requests."""
    LIBRARY = "library"
    """Favorites on real library items: recommendation seeds."""


class PlaceholderWrite(BaseModel):
    title: str
    year: int | None = None
    state: PlaceholderState = PlaceholderState.AVAILABLE

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v


class PlaceholderInfo(BaseModel):
    tmdb_id: int
    title: str
    state: PlaceholderState


class PlaceholdersResponse(BaseModel):
    media_type: MediaType
    placeholders: list[PlaceholderInfo]

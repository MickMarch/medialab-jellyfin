"""Request and response schemas for library endpoints."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UpdateType(str, Enum):
    CREATED = "Created"
    MODIFIED = "Modified"
    DELETED = "Deleted"


class MediaType(str, Enum):
    MOVIE = "movie"
    SHOW = "show"


class ScanRequest(BaseModel):
    path: str
    update_type: UpdateType = UpdateType.CREATED


class AddPathRequest(BaseModel):
    media_type: MediaType
    path: str
    refresh_library: bool = False
    library_name: str | None = None


class JellyfinVirtualFolder(BaseModel):
    """Jellyfin VirtualFolderInfo shape from GET /Library/VirtualFolders."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    collection_type: str | None = Field(alias="CollectionType", default=None)


class JellyfinItem(BaseModel):
    """Jellyfin BaseItemDto shape — subset of fields returned by GET /Items."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    type: str | None = Field(alias="Type", default=None)


class JellyfinItemsResult(BaseModel):
    """Jellyfin BaseItemDtoQueryResult shape from GET /Items."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[JellyfinItem] = Field(alias="Items", default_factory=list)
    total_record_count: int = Field(alias="TotalRecordCount", default=0)


class LibraryItem(BaseModel):
    id: str
    name: str
    type: str | None = None

    @classmethod
    def from_jellyfin(cls, item: JellyfinItem) -> "LibraryItem":
        return cls(id=item.id, name=item.name, type=item.type)


class ItemsResponse(BaseModel):
    items: list[LibraryItem]
    total_record_count: int

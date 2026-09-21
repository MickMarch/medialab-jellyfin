"""Request and response schemas for library endpoints."""

from enum import Enum

from medialab_contracts import MediaType
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UpdateType(str, Enum):
    CREATED = "Created"
    MODIFIED = "Modified"
    DELETED = "Deleted"


class ScanRequest(BaseModel):
    path: str
    update_type: UpdateType = UpdateType.CREATED

    @field_validator("path")
    @classmethod
    def path_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("path must not be empty")
        return v


class AddPathRequest(BaseModel):
    media_type: MediaType
    path: str
    refresh_library: bool = False
    library_name: str | None = None

    @field_validator("path")
    @classmethod
    def path_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("path must not be empty")
        return v

    @field_validator("library_name")
    @classmethod
    def library_name_must_not_be_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("library_name must not be empty if provided")
        return v


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

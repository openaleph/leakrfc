from datetime import datetime
from typing import Any, Generator, Literal, Self, TypeAlias

from anystore.mixins import BaseModel
from anystore.model import StoreModel
from anystore.store import get_store_for_uri
from anystore.store.base import Stats
from anystore.types import Uri
from anystore.util import SCHEME_FILE, make_data_checksum, name_from_uri
from ftmq.model import Dataset
from ftmq.util import make_proxy
from nomenklatura.dataset import DefaultDataset
from nomenklatura.entity import CE
from pydantic import field_validator, model_validator
from rigour.mime import DEFAULT

from leakrfc.util import guess_mimetype, mime_to_schema

ORIGIN_ORIGINAL = "original"
ORIGIN_EXTRACTED = "extracted"
ORIGIN_CONVERTED = "converted"

Origins: TypeAlias = Literal["original", "extracted", "converted"]


class ArchiveModel(BaseModel):
    uri: str | None = None
    metadata_prefix: str = ".leakrfc"
    public_url: str | None = None
    checksum_algorithm: str = "sha1"
    storage: StoreModel | None = None


class DatasetModel(Dataset):
    leakrfc: ArchiveModel = ArchiveModel()


class AbstractFileModel:
    def to_proxy(self) -> CE:
        proxy = make_proxy(
            {"id": self.id, "schema": mime_to_schema(self.mimetype)},
            dataset=self.dataset,
        )
        proxy.add("contentHash", self.content_hash)
        proxy.add("fileName", self.name)
        proxy.add("fileSize", self.size)
        proxy.add("mimeType", self.mimetype)
        return proxy

    @property
    def id(self) -> str:
        return (
            f"{self.dataset}-file-{make_data_checksum((self.key, self.content_hash))}"
        )


class File(Stats, AbstractFileModel):
    dataset: str
    content_hash: str
    mimetype: str | None = None
    processed: datetime | None = None
    origin: Origins = ORIGIN_ORIGINAL
    source_file: str | None = None
    extra: dict[str, Any] = {}

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        if hasattr(self, "origin"):
            data["origin"] = self.origin
        return data

    def to_document(self) -> "Document":
        return Document.from_file(self)

    @property
    def is_local(self) -> bool:
        return self.uri.startswith(SCHEME_FILE)

    @classmethod
    def from_info(cls, info: Stats, dataset: str, **data) -> Self:
        data["dataset"] = dataset
        return cls(**{**info.model_dump(), **data})

    @classmethod
    def from_uri(cls, uri: Uri, dataset: str | None = None, **data) -> Self:
        if dataset is None:
            dataset = DefaultDataset.name
        store, uri = get_store_for_uri(uri)
        return cls.from_info(store.info(uri), dataset, **data)

    @classmethod
    @field_validator("mimetype")
    def normalize_mimetype(cls, v: Any) -> str | None:
        return guess_mimetype(v)

    @model_validator(mode="after")
    def assign_mimetype(self):
        if self.mimetype in (None, DEFAULT):
            self.mimetype = guess_mimetype(self.name) or DEFAULT
        return self

    @model_validator(mode="after")
    def ensure_updated_at(self):
        self.updated_at = self.updated_at or self.created_at
        return self


class Document(BaseModel, AbstractFileModel):
    dataset: str
    key: str
    content_hash: str
    size: int
    mimetype: str
    created_at: datetime
    updated_at: datetime

    @property
    def name(self) -> str:
        return name_from_uri(self.key)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_created_at(cls, v: Any):
        return v or datetime.now()

    @field_validator("updated_at", mode="before")
    @classmethod
    def ensure_updated_at(cls, v: Any):
        return v or datetime.now()

    @classmethod
    def from_file(cls, file: File) -> Self:
        return cls(**file.model_dump())


Files: TypeAlias = Generator[File, None, None]
Docs: TypeAlias = Generator[Document, None, None]

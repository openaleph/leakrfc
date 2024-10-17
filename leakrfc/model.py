from datetime import datetime
from typing import Any, ClassVar, Generator, Self, TypeAlias

from anystore.mixins import BaseModel
from anystore.model import StoreModel
from anystore.store import get_store_for_uri
from anystore.store.base import Stats
from anystore.types import Uri
from anystore.util import make_data_checksum
from ftmq.util import make_proxy
from nomenklatura.dataset import DefaultDataset
from nomenklatura.entity import CE
from pantomime import DEFAULT
from pydantic import field_validator, model_validator

from leakrfc.util import guess_mimetype

ORIGIN_ORIGINAL = "original"
ORIGIN_EXTRACTED = "extracted"
ORIGIN_CONVERTED = "converted"


class ArchiveModel(BaseModel):
    uri: str | None = None
    metadata_prefix: str = ".leakrfc"
    public_url: str | None = None
    checksum_algorithm: str = "sha1"
    storage: StoreModel | None = None


class File(Stats):
    dataset: str
    content_hash: str
    mimetype: str | None = None
    processed: datetime | None = None
    extra: dict[str, Any] = {}

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        if hasattr(self, "origin"):
            data["origin"] = self.origin
        return data

    def to_proxy(self) -> CE:
        proxy = make_proxy({"id": self.id, "schema": "Document"}, dataset=self.dataset)
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


class OriginalFile(File):
    origin: ClassVar = ORIGIN_ORIGINAL


class ExtractedFile(File):
    origin: ClassVar = ORIGIN_EXTRACTED
    parent: str
    root: str


class ConvertedFile(File):
    origin: ClassVar = ORIGIN_CONVERTED
    root: str


OriginalFiles: TypeAlias = Generator[OriginalFile, None, None]
Files: TypeAlias = Generator[File, None, None]

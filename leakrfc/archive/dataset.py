from datetime import datetime
from functools import cached_property
from typing import BinaryIO, ClassVar, Iterable

import orjson
import yaml
from anystore.io import Uri, smart_open
from anystore.types import BytesGenerator, StrGenerator
from anystore.util import DEFAULT_HASH_ALGORITHM, clean_dict
from ftmq.model.coverage import Collector
from nomenklatura.entity import CE

from leakrfc.archive.base import BaseArchive
from leakrfc.archive.documents import Documents
from leakrfc.logging import get_logger
from leakrfc.model import ArchiveModel, DatasetModel, File, Files

log = get_logger(__name__)

INDEX = "index.json"
CONFIG = "config.yml"
INFO_PREFIX = "meta"
INFO = "info.json"
TXT = "txt"
ENTITIES_PREFIX = "entities"
ENTITIES = "entities.ftm.json"
DOCUMENTS = "documents.csv"


class ReadOnlyDatasetArchive(BaseArchive):
    readonly: ClassVar = True
    name: str

    def exists(self, key: str) -> bool:
        path = self._get_file_info_path(key)
        return self._storage.exists(path)

    def make_checksum(
        self, key: str, algorithm: str | None = DEFAULT_HASH_ALGORITHM
    ) -> str:
        return self._storage.checksum(self._make_path(key), algorithm)

    def lookup_file(self, key: str) -> File:
        path = self._get_file_info_path(key)
        return self._storage.get(path, model=File)

    def stream_file(self, file: File) -> BytesGenerator:
        yield from self._storage.stream(self._make_path(file.key))

    def open_file(self, file: File) -> BinaryIO:
        return self._storage.open(self._make_path(file.key))

    def iter_files(self, use_db: bool | None = True) -> Files:
        if use_db:
            for doc in self.documents:
                yield self.lookup_file(doc.key)
        else:
            prefix = self._make_path(self.metadata_prefix, INFO_PREFIX)
            for key in self._storage.iterate_keys(prefix=prefix):
                yield self._storage.get(key, model=File)

    def iter_keys(self) -> StrGenerator:
        for key in self._storage.iterate_keys(
            prefix=self._make_path(),
            exclude_prefix=self._make_path(self.metadata_prefix),
        ):
            if self.is_zip:
                key = key[len(self.name) + 1 :]
            yield key

    @cached_property
    def documents(self) -> Documents:
        return Documents(self)

    @cached_property
    def config(self) -> DatasetModel:
        uri = self._get_config_path()
        if not self._storage.exists(uri):
            return DatasetModel(
                name=self.name, leakrfc=ArchiveModel(**self.model_dump())
            )
        uri = self._storage.get_key(self._get_config_path())
        return DatasetModel.from_yaml_uri(uri)

    def _get_file_info_path(self, key) -> str:
        return self._make_path(self.metadata_prefix, INFO_PREFIX, key, INFO)

    def _get_documents_path(self, now: bool = False, suffix: str | None = None) -> str:
        path = DOCUMENTS
        if now:
            suffix = datetime.now().isoformat()
        if suffix:
            path += f".{suffix}"
        return self._make_path(self.metadata_prefix, path)

    def _get_entities_path(self, now: bool = False, suffix: str | None = None) -> str:
        path = ENTITIES
        if now:
            suffix = datetime.now().isoformat()
        if suffix:
            path += f".{suffix}"
        return self._make_path(self.metadata_prefix, ENTITIES_PREFIX, path)

    def _get_config_path(self) -> str:
        return self._make_path(self.metadata_prefix, CONFIG)

    def _get_index_path(self) -> str:
        return self._make_path(self.metadata_prefix, INDEX)

    def _make_path(self, *parts: str) -> str:
        if self.is_zip:
            parts = tuple([self.name, *parts])
        return super()._make_path(*parts)


class DatasetArchive(ReadOnlyDatasetArchive):
    readonly: ClassVar = False

    def archive_file(
        self, file: File, from_uri: Uri | None = None, copy: bool | None = True
    ) -> File:
        """Add the given file to the archive. This doesn't check for existing
        files or if the given `file.content_hash` is correct. This should be
        handled in higher logic, as seen in `leakrfc.make.make_dataset`."""

        uri = from_uri or file.uri

        # store actual file
        if copy:
            file_path = self._make_path(file.key)
            with smart_open(uri, "rb") as i:
                with self._storage.open(file_path, mode="wb") as o:
                    o.write(i.read())

        # adjust metadata
        file.store = self._storage.uri
        file.dataset = self.name

        # store metadata
        self._put_file_info(file)

        log.info(
            f"Added `{file.key} ({file.content_hash})`",
            dataset=self.name,
            from_uri=uri,
            to_store=self._storage.uri,
        )
        return file

    def add_proxies(self, proxies: Iterable[CE]) -> None:
        path = self._get_entities_path()
        data = b"\n".join([orjson.dumps(p.to_full_dict()) for p in proxies])
        self._storage.put(path, data)

    def delete_file(self, key: str) -> None:
        self._storage.delete(self._get_file_info_path(key), ignore_errors=True)
        self._storage.delete(key, ignore_errors=True)

    def _put_file_info(self, file):
        # store file metadata in storage and cache
        self._storage.put(self._get_file_info_path(file.key), file, model=File)
        self.documents.add(file.to_document())

    def make_config(self, data: DatasetModel | None = None) -> DatasetModel:
        uri = self._get_config_path()
        data = data or self.config
        # FIXME
        obj = clean_dict(data.model_dump(mode="json"))
        self._storage.put(
            uri,
            obj,
            serialization_mode="auto",
            serialization_func=yaml.safe_dump,
        )
        return data

    def make_index(
        self, data: DatasetModel | None = None, collect_stats: bool | None = True
    ) -> str:
        data = data or self.make_config()
        if collect_stats:
            collector = Collector()
            collector.collect_many(self.documents.iter_entities())
            data.apply_stats(collector.export())
            data.total_file_size = self.make_size()
        obj = clean_dict(data.model_dump(mode="json"))
        self._storage.put(
            self._get_index_path(), orjson.dumps(obj, option=orjson.OPT_APPEND_NEWLINE)
        )
        return self._storage.get_key(self._get_index_path())

    def make_size(self) -> int:
        size = self.documents.get_total_size()
        uri = self._make_path(self.metadata_prefix, "size")
        self._storage.put(uri, size, serialization_mode="auto")
        return size

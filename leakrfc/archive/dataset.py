from datetime import datetime
from typing import Any, BinaryIO, ClassVar, Iterable

import orjson
from anystore.store.base import BaseStore
from anystore.store.virtual import get_virtual
from anystore.types import BytesGenerator
from banal import ensure_dict
from nomenklatura.entity import CE

from leakrfc.archive.base import Archive, BaseArchive, get_store
from leakrfc.logging import get_logger
from leakrfc.model import OriginalFile, OriginalFiles
from leakrfc.util import make_ch_key

log = get_logger(__name__)

INFO_PREFIX = "info"
INFO = "info.json"
STORE_PREFIX = "store"
KEY = "key"
TXT = "txt"
ENTITIES_PREFIX = "entities"
ENTITIES = "entities.ftm.json"


class ReadOnlyDatasetArchive(BaseArchive):
    readonly: ClassVar = True
    name: str
    archive: Archive

    def exists(self, key: str) -> bool:
        path = self._get_file_info_path(key)
        return self._meta_storage.exists(path)

    def exists_hash(self, content_hash: str) -> bool:
        lookup_key = self._join_path(STORE_PREFIX, make_ch_key(content_hash), KEY)
        key = self._meta_storage.get(lookup_key)
        return self.exists(key)

    def lookup_file(self, key: str) -> OriginalFile:
        path = self._get_file_info_path(key)
        return self._meta_storage.get(path, model=OriginalFile)

    def lookup_file_by_hash(self, content_hash: str) -> OriginalFile:
        key_path = self._join_path(STORE_PREFIX, make_ch_key(content_hash), KEY)
        key = self._meta_storage.get(key_path)
        return self.lookup_file(key)

    def stream_file(self, file: OriginalFile) -> BytesGenerator:
        yield from self._storage.stream(file.key)

    def open_file(self, file: OriginalFile) -> BinaryIO:
        return self._storage.open(file.key)

    def iter_files(self) -> OriginalFiles:
        for key in self._meta_storage.iterate_keys(INFO_PREFIX):
            yield self._meta_storage.get(key, model=OriginalFile)

    def _get_file_info_path(self, key, with_prefix: bool = False) -> str:
        path = self._join_path(INFO_PREFIX, key, INFO)
        if with_prefix:
            path = self._join_path(self.metadata_prefix, path)
        return path

    def _get_file_store_path(self, key: str, *parts: str) -> str:
        file = self.lookup_file(key)
        return self._join_path(STORE_PREFIX, make_ch_key(file.content_hash), *parts)

    def _get_entities_path(
        self, now: bool = False, suffix: str | None = None, with_prefix: bool = False
    ) -> str:
        path = ENTITIES
        if now:
            suffix = datetime.now().isoformat()
        if suffix:
            path += f".{suffix}"
        path = self._join_path(ENTITIES_PREFIX, path)
        if with_prefix:
            path = self._join_path(self.metadata_prefix, path)
        return path


class DatasetArchive(ReadOnlyDatasetArchive):
    readonly: ClassVar = False

    def archive_file(
        self,
        uri: str,
        store: BaseStore | None = None,
        file: OriginalFile | None = None,
        data: dict[str, Any] | None = None,
    ) -> OriginalFile:
        """Add the given file to the archive. This doesn't check for existing
        files or if the given `file.content_hash` is correct. This should be
        handled in higher logic, as seen in `leakrfc.make.make_dataset`."""

        if store is None:
            store_uri, uri = uri.rsplit("/", 1)
            store = get_store(uri=store_uri)
        log.debug(
            "Adding file ...",
            uri=uri,
            dataset=self.name,
            from_store=store.uri,
            to_store=self._storage.uri,
        )

        with get_virtual(prefix=f"leakrfc-{self.name}-") as tmp:
            tmp_path = tmp.download(uri, store)
            if file is not None:
                content_hash = file.content_hash
            else:
                content_hash = tmp.store.checksum(tmp_path, self.checksum_algorithm)

            if file is None:
                file = OriginalFile.from_info(
                    store.info(uri), dataset=self.name, content_hash=content_hash
                )
            file_data = file.model_dump()
            file_data.update(
                {
                    **ensure_dict(data),
                    "content_hash": content_hash,
                    "dataset": self.name,
                    "store": self._storage.uri,
                }
            )
            file = OriginalFile(**file_data)
            # store actual file
            with tmp.store.open(tmp_path) as i:
                with self._storage.open(file.key, mode="wb") as o:
                    o.write(i.read())
            # store metadata
            self._put_file_info(file)

        log.info(
            f"Added `{file.key} ({content_hash})`",
            uri=uri,
            dataset=self.name,
            from_store=store.uri,
            to_store=self._storage.uri,
        )
        return file

    def _put_file_info(self, file: OriginalFile) -> None:
        # store metadata
        self._meta_storage.put(
            self._get_file_info_path(file.key), file, model=OriginalFile
        )
        # store hash reverse lookup
        self._meta_storage.put(
            self._get_file_store_path(file.key, KEY), file.key.encode()
        )

    def add_proxies(self, proxies: Iterable[CE]) -> None:
        path = self._get_entities_path()
        data = b"\n".join([orjson.dumps(p.to_full_dict()) for p in proxies])
        self._meta_storage.put(path, data)

    def delete_file(self, key: str) -> None:
        self._meta_storage.delete(self._get_file_info_path(key), ignore_errors=True)
        self._storage.delete(key, ignore_errors=True)

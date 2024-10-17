"""
Convert a "memorious collection" (the output format of the store->directory
stage) into a leakrfc dataset

memorious format:
    ./data/store/test_dataset/
        ./<sha1>.data.pdf|doc|...  # actual file
        ./<sha1>.json              # metadata file
"""

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from anystore import anycache
from anystore.store import get_store
from anystore.types import StrGenerator, Uri
from anystore.util import make_data_checksum

from leakrfc.archive import DatasetArchive
from leakrfc.archive.cache import get_cache
from leakrfc.logging import get_logger
from leakrfc.model import OriginalFile
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


def make_cache_key(self: "MemoriousWorker", key: str) -> str | None:
    if not self.use_cache:
        return
    host = urlparse(self.memorious.uri).netloc
    if host is None:
        host = make_data_checksum(str(self.memorious.uri))
    return f"memorious/sync/{host}/{self.dataset.name}/{key}"


def get_file_key(data: dict[str, Any]) -> str:
    return urlparse(data["url"]).path


class MemoriousWorker(DatasetWorker):
    def __init__(
        self, uri: Uri, key_func: Callable | None = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.memorious = get_store(uri, serialization_mode="raw")
        self.key_func = key_func or get_file_key

    def get_tasks(self) -> StrGenerator:
        yield from self.memorious.iterate_keys(glob="*.json")

    def handle_task(self, task: str) -> None:
        file = self.load_memorious(task)
        if file is not None:
            if not self.dataset.exists(file.key):
                self.dataset.archive_file(
                    file.extra.pop("_file_name"),
                    store=self.memorious,
                    file=file,
                )
            else:
                self.log_info(
                    f"Skipping already existing `{file.key}` ...",
                    store=self.memorious.uri,
                )

    @anycache(store=get_cache(), key_func=make_cache_key, model=OriginalFile)
    def load_memorious(self, key: str) -> OriginalFile | None:
        data = self.memorious.get(key, serialization_mode="json")
        content_hash = data.pop("content_hash", None)
        if content_hash is None:
            log.warning(f"No content hash for `{key}`", store=self.memorious.uri)
        elif data.get("_file_name") is None:
            log.warning(f"No original file for `{key}`", store=self.memorious.uri)
        else:
            key = self.key_func(data)
            info = self.memorious.info(data["_file_name"])
            return OriginalFile(
                key=key.strip("/"),
                name=Path(key).name,
                size=info.size,
                content_hash=content_hash,
                store=str(self.memorious.uri),
                dataset=self.dataset.name,
                extra=data,
            )

    def done(self) -> None:
        self.log_info(f"Done memorious import from `{self.memorious.uri}`")


def import_memorious(
    dataset: DatasetArchive, uri: Uri, key_func: Callable | None = None
) -> None:
    worker = MemoriousWorker(uri, key_func, dataset=dataset)
    worker.log_info(f"Starting memorious import from `{worker.memorious.uri}` ...")
    worker.run()

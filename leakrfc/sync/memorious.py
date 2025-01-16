from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from anystore import anycache
from anystore.store import get_store
from anystore.types import StrGenerator, Uri
from anystore.util import make_data_checksum
from anystore.worker import WorkerStatus

from leakrfc.archive import DatasetArchive
from leakrfc.archive.cache import get_cache
from leakrfc.logging import get_logger
from leakrfc.model import File
from leakrfc.util import render
from leakrfc.worker import DatasetWorker, make_cache_key

log = get_logger(__name__)


def get_cache_key(self: "MemoriousWorker", key: str) -> str | None:
    host = urlparse(self.memorious.uri).netloc
    if host is None:
        host = make_data_checksum(str(self.memorious.uri))
    return make_cache_key(self, "sync", "memorious", host, key)


class MemoriousStatus(WorkerStatus):
    added: int = 0
    skipped: int = 0
    not_found: int = 0


class MemoriousWorker(DatasetWorker):
    def __init__(
        self, uri: Uri, key_func: Callable | None = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.memorious = get_store(uri, serialization_mode="raw")
        self.key_func = key_func or get_file_key
        self.status_model = MemoriousStatus

    def get_tasks(self) -> StrGenerator:
        yield from self.memorious.iterate_keys(glob="*.json")

    @anycache(store=get_cache(), key_func=get_cache_key)
    def handle_task(self, task: str) -> datetime:
        now = datetime.now()
        file = self.load_memorious(task)
        if file is not None:
            if not self.dataset.exists(file.key):
                uri = self.memorious.get_key(file.extra.pop("_file_name"))
                self.dataset.archive_file(file, from_uri=uri)
                self.count(added=1)
            else:
                self.log_info(
                    f"Skipping already existing `{file.key}` ...",
                    store=self.memorious.uri,
                )
                self.count(skipped=1)
        return now

    def load_memorious(self, key: str) -> File | None:
        data = self.memorious.get(key, serialization_mode="json")
        content_hash = data.pop("content_hash", None)
        if content_hash is None:
            log.warning(f"No content hash for `{key}`", store=self.memorious.uri)
            self.count(not_found=1)
        elif data.get("_file_name") is None:
            log.warning(f"No original file for `{key}`", store=self.memorious.uri)
            self.count(not_found=1)
        else:
            key = self.key_func(data)
            info = self.memorious.info(data["_file_name"])
            return File(
                key=key.strip("/"),
                name=Path(key).name,
                size=info.size,
                content_hash=content_hash,
                store=str(self.memorious.uri),
                dataset=self.dataset.name,
                extra=data,
            )

    def done(self) -> None:
        documents = self.dataset.documents.write()
        self.dataset.make_index()
        self.dataset.make_size()
        self.log_info(
            f"Done memorious import from `{self.memorious.uri}`", documents=documents
        )


def import_memorious(
    dataset: DatasetArchive,
    uri: Uri,
    key_func: Callable | None = None,
    use_cache: bool | None = True,
) -> MemoriousStatus:
    """
    Convert a "memorious collection" (the output format of the store->directory
    stage) into a leakrfc dataset

    memorious store:
        ```
        ./data/store/test_dataset/
            ./<sha1>.data.pdf|doc|...  # actual file
            ./<sha1>.json              # metadata file
        ```

    The memorious json metadata for each file will be stored in the leakrfc
    metadata at the `extra` property for each file.

    Args:
        dataset: leakrfc Dataset instance
        uri: local or remote location of the memorious store that supports file
            listing
        key_func: A function to generate file keys (their relative paths), per
            default it is generated from the source url.
        use_cache: Use global processing cache to skip tasks
    """

    worker = MemoriousWorker(uri, key_func, dataset=dataset, use_cache=use_cache)
    worker.log_info(f"Starting memorious import from `{worker.memorious.uri}` ...")
    return worker.run()


def get_file_key(data: dict[str, Any]) -> str:
    return unquote(urlparse(data["url"]).path).strip("/")


def get_file_name(data: dict[str, Any]) -> str:
    return unquote(Path(urlparse(data["url"]).path).name)


def get_file_name_templ_func(tmpl: str) -> Callable:
    def _func(data: dict[str, Any]) -> str:
        return render(tmpl, data)

    return _func


def get_file_name_strip_func(strip_prefix: str) -> Callable:
    def _func(data: dict[str, Any]) -> str:
        return get_file_key(data)[len(strip_prefix) :].strip("/")

    return _func

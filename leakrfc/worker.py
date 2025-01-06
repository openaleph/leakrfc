import contextlib
from typing import TYPE_CHECKING, Any

from anystore.store import BaseStore, get_store_for_uri
from anystore.store.virtual import get_virtual
from anystore.worker import Worker

from leakrfc.logging import get_logger
from leakrfc.model import File
from leakrfc.settings import ArchiveSettings, Settings

if TYPE_CHECKING:
    from leakrfc.archive.dataset import DatasetArchive


log = get_logger(__name__)

settings = Settings()
leakrfc_settings = ArchiveSettings()


def make_cache_key(worker: "DatasetWorker", action: str, *extra: str) -> str | None:
    if not worker.use_cache:
        return
    return f"{leakrfc_settings.cache_prefix}/{worker.dataset.name}/{action}/{'/'.join(extra)}"


class DatasetWorker(Worker):
    def __init__(
        self, dataset: "DatasetArchive", use_cache: bool | None = True, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.dataset = dataset
        self.use_cache = use_cache

    def get_tasks(self) -> Any:
        yield from self.dataset.iter_files()

    def log_info(self, msg: str, **ctx) -> None:
        ctx = {
            "dataset": self.dataset.name,
            "storage": self.dataset._storage.uri,
            **ctx,
        }
        log.info(msg, **ctx)

    def log_warning(self, msg: str, **ctx) -> None:
        ctx = {
            "dataset": self.dataset.name,
            "storage": self.dataset._storage.uri,
            **ctx,
        }
        log.warning(msg, **ctx)

    def log_error(self, msg: str, **ctx) -> None:
        ctx = {
            "dataset": self.dataset.name,
            "storage": self.dataset._storage.uri,
            **ctx,
        }
        log.error(msg, **ctx)

    def exception(self, task: Any, e: Exception) -> None:
        self.log_error(
            f"Error while handling task: {e.__class__.__name__}: {e}",
            task=task,
        )
        if settings.debug:
            raise e

    @contextlib.contextmanager
    def local_file(self, uri: str, store: BaseStore | None):
        """
        Get a `File` instance pointing to a file in the local
        filesystem.

        If the source is local as well, use the actual file. If the source is
        remote, use a temporary downloaded version of the file.
        """
        tmp = None
        if store is None:
            store, uri = get_store_for_uri(uri)
        if not store.is_local:
            tmp = get_virtual()
            uri = tmp.download(uri, store)
            store = tmp.store

        info = store.info(uri)
        content_hash = store.checksum(uri)
        file = File.from_info(info, self.dataset.name, content_hash=content_hash)
        # file.name = name_from_uri(uri)
        try:
            yield file
        finally:
            if tmp is not None:
                tmp.cleanup()

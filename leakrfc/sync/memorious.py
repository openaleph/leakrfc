"""
Convert a "memorious collection" (the output format of the store->directory
stage) into a leakrfc dataset

memorious format:
    ./data/store/test_dataset/
        ./<sha1>.data.pdf|doc|...  # actual file
        ./<sha1>.json              # metadata file
"""

from pathlib import Path
from urllib.parse import urlparse

from anystore.store import BaseStore, get_store
from anystore.types import Uri

from leakrfc.archive import DatasetArchive
from leakrfc.logging import get_logger
from leakrfc.model import OriginalFile, OriginalFiles
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


def iter_memorious(store: BaseStore, dataset: str) -> OriginalFiles:
    for key in store.iterate_keys():
        if key.endswith(".json"):
            data = store.get(key, serialization_mode="json")
            content_hash = data.pop("content_hash", None)
            if content_hash is None:
                log.warning(f"No content hash for `{key}`", store=store.uri)
            elif data.get("_file_name") is None:
                log.warning(f"No original file for `{key}`", store=store.uri)
            else:
                parsed = urlparse(data["url"])
                p = Path(parsed.path)
                info = store.info(data["_file_name"])
                yield OriginalFile(
                    key=str(p).lstrip("/"),
                    name=p.name,
                    path=str(p.parent).lstrip("/"),
                    size=info.size,
                    content_hash=content_hash,
                    store=str(store.uri),
                    dataset=dataset,
                    extra=data,
                )


class MemoriousWorker(DatasetWorker):
    def __init__(self, uri: Uri, dataset: DatasetArchive, *args, **kwargs) -> None:
        super().__init__(dataset, *args, **kwargs)
        self.memorious = get_store(uri, serialization_mode="raw")

    def get_tasks(self) -> OriginalFiles:
        yield from iter_memorious(self.memorious, self.dataset.name)

    def handle_task(self, task: OriginalFile) -> None:
        self.dataset.archive_file(
            task.extra.pop("_file_name"),
            store=self.memorious,
            file=task,
        )

    def done(self) -> None:
        self.log_info(f"Done memorious import from `{self.memorious.uri}`")


def import_memorious(dataset: DatasetArchive, uri: Uri) -> None:
    worker = MemoriousWorker(uri, dataset)
    worker.log_info(f"Starting memorious import from `{worker.memorious.uri}` ...")
    worker.run()

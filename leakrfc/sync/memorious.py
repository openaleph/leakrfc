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

from anystore.store import get_store
from anystore.types import StrGenerator, Uri

from leakrfc.archive import DatasetArchive
from leakrfc.logging import get_logger
from leakrfc.model import OriginalFile
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


class MemoriousWorker(DatasetWorker):
    def __init__(self, uri: Uri, dataset: DatasetArchive, *args, **kwargs) -> None:
        super().__init__(dataset, *args, **kwargs)
        self.memorious = get_store(uri, serialization_mode="raw")

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

    def load_memorious(self, key: str) -> OriginalFile | None:
        data = self.memorious.get(key, serialization_mode="json")
        content_hash = data.pop("content_hash", None)
        if content_hash is None:
            log.warning(f"No content hash for `{key}`", store=self.memorious.uri)
        elif data.get("_file_name") is None:
            log.warning(f"No original file for `{key}`", store=self.memorious.uri)
        else:
            parsed = urlparse(data["url"])
            p = Path(parsed.path)
            info = self.memorious.info(data["_file_name"])
            return OriginalFile(
                key=str(p).lstrip("/"),
                name=p.name,
                path=str(p.parent).lstrip("/"),
                size=info.size,
                content_hash=content_hash,
                store=str(self.memorious.uri),
                dataset=self.dataset.name,
                extra=data,
            )

    def done(self) -> None:
        self.log_info(f"Done memorious import from `{self.memorious.uri}`")


def import_memorious(dataset: DatasetArchive, uri: Uri) -> None:
    worker = MemoriousWorker(uri, dataset)
    worker.log_info(f"Starting memorious import from `{worker.memorious.uri}` ...")
    worker.run()

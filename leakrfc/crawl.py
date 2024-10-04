"""
Crawl document collections from public accessible archives (or local folders)
"""

from typing import Generator

from anystore import get_store
from anystore.store import BaseStore
from anystore.types import Uri

from leakrfc.archive import DatasetArchive
from leakrfc.logging import get_logger
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


class CrawlWorker(DatasetWorker):
    def __init__(self, remote: BaseStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self.remote = remote

    def get_tasks(self) -> Generator[str, None, None]:
        self.log_info(f"Crawling `{self.remote.uri}` ...")
        yield from self.remote.iterate_keys()

    def handle_task(self, task: str) -> None:
        self.log_info(f"Crawling `{task}` ...", remote=self.remote.uri)
        self.dataset.archive_file(task, self.remote)

    def done(self) -> None:
        self.log_info(f"Crawling `{self.remote.uri}`: Done.")


def crawl(uri: Uri, storage: DatasetArchive) -> None:
    remote_store = get_store(uri=uri, serialization_mode="raw")
    worker = CrawlWorker(remote_store, dataset=storage)
    worker.run()

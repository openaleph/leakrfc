"""
Crawl document collections from public accessible archives (or local folders)
"""

from datetime import datetime
from fnmatch import fnmatch
from typing import Generator

import aiohttp
from anystore import anycache, get_store
from anystore.store import BaseStore
from anystore.types import Uri
from anystore.worker import WorkerStatus
from banal import ensure_dict

from ftm_datalake.archive import DatasetArchive
from ftm_datalake.archive.cache import get_cache
from ftm_datalake.logging import get_logger
from ftm_datalake.model import ORIGIN_ORIGINAL, File, Origins
from ftm_datalake.worker import DatasetWorker, make_cache_key

log = get_logger(__name__)


def get_cache_key(self: "CrawlWorker", key: str) -> str | None:
    return make_cache_key(self, "crawl", key)


class CrawlStatus(WorkerStatus):
    packages: int = 0


class CrawlWorker(DatasetWorker):
    def __init__(
        self,
        remote: BaseStore,
        skip_existing: bool | None = True,
        write_documents_db: bool | None = False,
        exclude: str | None = None,
        include: str | None = None,
        origin: Origins | None = ORIGIN_ORIGINAL,
        source_file: File | None = None,
        **kwargs,
    ) -> None:
        kwargs["status_model"] = kwargs.get("status_model", CrawlStatus)
        super().__init__(**kwargs)
        self.remote = remote
        self.skip_existing = skip_existing
        self.write_documents_db = write_documents_db
        self.exclude = exclude
        self.include = include
        self.origin = origin or ORIGIN_ORIGINAL
        self.source_file = source_file

    def get_tasks(self) -> Generator[str, None, None]:
        self.log_info(f"Crawling `{self.remote.uri}` ...")
        for key in self.remote.iterate_keys():
            if self.exclude and fnmatch(key, self.exclude):
                continue
            if self.include and not fnmatch(key, self.include):
                continue
            yield key

    @anycache(store=get_cache(), key_func=get_cache_key)
    def handle_task(self, task: str) -> datetime:
        now = datetime.now()
        if self.skip_existing and self.dataset.exists(task):
            self.log_info(
                f"Skipping already existing `{task}` ...", remote=self.remote.uri
            )
            return now
        self.log_info(
            f"Crawling `{task}` ...",
            remote=self.remote.uri,
            origin=self.origin,
            source=self.source_file.key if self.source_file else None,
        )
        with self.local_file(task, self.remote) as file:
            file.origin = self.origin
            if self.source_file:
                file.source_file = self.source_file.key
            else:
                self.dataset.archive_file(file)
        return now

    def crawl_child(
        self,
        uri: Uri,
        origin: Origins | None = ORIGIN_ORIGINAL,
        source_file: File | None = None,
    ) -> CrawlStatus:
        return crawl(
            uri,
            dataset=self.dataset,
            skip_existing=self.skip_existing,
            write_documents_db=False,
            origin=origin,
            source_file=source_file,
        )

    def done(self) -> None:
        if self.write_documents_db:
            documents = self.dataset.documents.write()
            self.dataset.make_index()
            self.dataset.make_size()
            self.log_info(f"Crawling `{self.remote.uri}`: Done.", documents=documents)


def crawl(
    uri: Uri,
    dataset: DatasetArchive,
    skip_existing: bool | None = True,
    write_documents_db: bool | None = True,
    exclude: str | None = None,
    include: str | None = None,
    origin: Origins | None = ORIGIN_ORIGINAL,
    source_file: File | None = None,
) -> CrawlStatus:
    """
    Crawl a local or remote location of documents into a ftm_datalake dataset.

    Args:
        uri: local or remote location uri that supports file listing
        dataset: ftm_datalake Dataset instance
        skip_existing: Don't re-crawl existing keys (doesn't check for checksum)
        write_documents_db: Create csv-based document tables at the end of crawl run
        exclude: Exclude glob for file paths not to crawl
        include: Include glob for file paths to crawl
        origin: Origin of files (used for sub runs of crawl within a crawl job)
        source_file: Source file (used for sub runs of crawl within a crawl job)
    """
    remote_store = get_store(uri=uri)
    # FIXME ensure long timeouts
    if remote_store.scheme.startswith("http"):
        backend_config = ensure_dict(remote_store.backend_config)
        backend_config["client_kwargs"] = {
            **ensure_dict(backend_config.get("client_kwargs")),
            "timeout": aiohttp.ClientTimeout(total=3600 * 24),
        }
        remote_store.backend_config = backend_config
    worker = CrawlWorker(
        remote_store,
        dataset=dataset,
        skip_existing=skip_existing,
        write_documents_db=write_documents_db,
        exclude=exclude,
        include=include,
        origin=origin,
        source_file=source_file,
    )
    return worker.run()

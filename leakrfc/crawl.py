"""
Crawl document collections from public accessible archives (or local folders)
"""

from fnmatch import fnmatch
from typing import Generator

from anystore import anycache, get_store
from anystore.store import BaseStore
from anystore.types import Uri
from anystore.util import rm_rf
from anystore.worker import WorkerStatus

from leakrfc.archive import DatasetArchive
from leakrfc.archive.cache import get_cache
from leakrfc.extract import handle_extract, is_archive
from leakrfc.logging import get_logger
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


def get_cache_key(self: "CrawlWorker", key: str) -> str | None:
    if self.use_cache:
        return f"crawl/{self.dataset.name}/{key}"


class CrawlStatus(WorkerStatus):
    packages: int = 0
    extracted: int = 0


class CrawlWorker(DatasetWorker):
    def __init__(
        self,
        remote: BaseStore,
        skip_existing: bool | None = True,
        extract: bool | None = False,
        extract_keep_source: bool | None = False,
        write_documents_db: bool | None = False,
        exclude: str | None = None,
        include: str | None = None,
        **kwargs,
    ) -> None:
        kwargs["status_model"] = kwargs.get("status_model", CrawlStatus)
        super().__init__(**kwargs)
        self.remote = remote
        self.skip_existing = skip_existing
        self.extract = extract
        self.extract_keep_source = extract_keep_source
        self.write_documents_db = write_documents_db
        self.exclude = exclude
        self.include = include

    def get_tasks(self) -> Generator[str, None, None]:
        self.log_info(f"Crawling `{self.remote.uri}` ...")
        for key in self.remote.iterate_keys():
            if self.exclude or self.include:
                if self.exclude and not fnmatch(key, self.exclude):
                    yield key
                elif self.include and fnmatch(key, self.include):
                    yield key
            else:
                yield key

    @anycache(store=get_cache(), key_func=get_cache_key)
    def handle_task(self, task: str) -> None:
        if self.skip_existing and self.dataset.exists(task):
            self.log_info(
                f"Skipping already existing `{task}` ...", remote=self.remote.uri
            )
            return
        self.log_info(f"Crawling `{task}` ...", remote=self.remote.uri)
        with self.local_file(task, self.remote) as file:
            if self.extract and is_archive(file):
                self.count(packages=1)
                out = handle_extract(file)
                if out is not None:
                    res = self.crawl_child(out)
                    self.count(extracted=res.done)
                    self.count(errors=res.errors)
                    rm_rf(out)
                if self.extract_keep_source:
                    self.dataset.archive_file(file)
            else:
                self.dataset.archive_file(file)

    def crawl_child(self, uri: Uri) -> CrawlStatus:
        return crawl(
            uri,
            storage=self.dataset,
            skip_existing=self.skip_existing,
            extract=self.extract,
            extract_keep_source=self.extract_keep_source,
            write_documents_db=False,
        )

    def done(self) -> None:
        if self.write_documents_db:
            documents = self.dataset.documents.write()
            self.log_info(f"Crawling `{self.remote.uri}`: Done.", documents=documents)


def crawl(
    uri: Uri,
    storage: DatasetArchive,
    skip_existing: bool | None = True,
    extract: bool | None = False,
    extract_keep_source: bool | None = False,
    use_cache: bool | None = True,
    write_documents_db: bool | None = True,
    exclude: str | None = None,
    include: str | None = None,
) -> CrawlStatus:
    remote_store = get_store(uri=uri, serialization_mode="raw")
    worker = CrawlWorker(
        remote_store,
        dataset=storage,
        skip_existing=skip_existing,
        extract=extract,
        extract_keep_source=extract_keep_source,
        use_cache=use_cache,
        write_documents_db=write_documents_db,
        exclude=exclude,
        include=include,
    )
    return worker.run()

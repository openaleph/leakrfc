"""
Make or update a leakrfc dataset and check integrity
"""

from datetime import datetime
from typing import Generator, Literal, TypeAlias

from anystore.decorators import anycache
from anystore.exceptions import DoesNotExist
from anystore.worker import WorkerStatus

from leakrfc.archive.cache import get_cache
from leakrfc.archive.dataset import DatasetArchive
from leakrfc.worker import DatasetWorker, make_cache_key


class MakeStatus(WorkerStatus):
    files_total: int = 0
    metadata_total: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    integrity_errors: int = 0


ACTION_SOURCE = "source"
ACTION_INFO = "info"
Action: TypeAlias = Literal["info", "source"]
Task: TypeAlias = tuple[str, Action]


def get_cache_key(self: "MakeWorker", task: Task) -> str | None:
    key, action = task
    return make_cache_key(self, "make", action, key)


class MakeWorker(DatasetWorker):
    def __init__(
        self,
        check_integrity: bool | None = True,
        cleanup: bool | None = True,
        metadata_only: bool | None = False,
        *args,
        **kwargs,
    ) -> None:
        kwargs["status_model"] = kwargs.get("status_model", MakeStatus)
        super().__init__(*args, **kwargs)
        self.check_integrity = check_integrity if not metadata_only else False
        self.cleanup = cleanup
        self.metadata_only = metadata_only

    def get_tasks(self) -> Generator[Task, None, None]:
        if not self.metadata_only:
            self.log_info("Checking source files ...")
            for key in self.dataset.iter_keys():
                self.count(files_total=1)
                yield key, ACTION_SOURCE
        self.log_info("Checking existing files ...")
        for file in self.dataset.iter_files(use_db=False):
            self.count(metadata_total=1)
            yield file.key, ACTION_INFO

    @anycache(store=get_cache(), key_func=get_cache_key)
    def handle_task(self, task: Task) -> str:
        now = datetime.now().isoformat()
        key, action = task
        if action == ACTION_SOURCE:
            self.log_info(f"Checking `{key}` ...", action=action)
            if not self.dataset.exists(key):
                with self.local_file(key, self.dataset._storage) as file:
                    self.dataset.archive_file(file, copy=False)
                self.count(files_added=1)
        elif action == ACTION_INFO:
            self.log_info(f"Checking `{key}` metadata ...", action=action)
            self._ensure_integrity(key)
        return now

    def _ensure_integrity(self, key: str) -> None:
        if self.check_integrity:
            self.count(files_checked=1)
            self.log_info(f"Testing checksum for `{key}` ...")
            file = self.dataset.lookup_file(key)
            try:
                content_hash = self.dataset.make_checksum(key)
                if content_hash != file.content_hash:
                    self.log_error(
                        f"Checksum mismatch for `{key}`: `{content_hash}`",
                        file=file,
                    )
                    self.count(integrity_errors=1)
                    if self.cleanup:
                        self.log_info(f"Fixing checksum for `{key}` ...")
                        file.content_hash = content_hash
                        self.dataset._put_file_info(file)
                self.dataset.documents.add(file.to_document())
            except DoesNotExist:
                self.log_error(f"Source file `{key}` does not exist")
                self.count(files_deleted=1)
                if self.cleanup:
                    self.log_info(f"Deleting metadata for `{key}` ...")
                    self.dataset.delete_file(key)
                    self.dataset.documents.delete(file.to_document())
        else:
            # still (re)build documents database
            file = self.dataset.lookup_file(key)
            self.dataset.documents.add(file.to_document())

    def done(self) -> None:
        self.dataset.documents.write()
        self.dataset.make_index()
        self.dataset.make_size()


def make_dataset(
    dataset: DatasetArchive,
    use_cache: bool | None = True,
    check_integrity: bool | None = True,
    cleanup: bool | None = True,
    metadata_only: bool | None = False,
) -> MakeStatus:
    """
    Make or update a leakrfc dataset and optionally check its integrity.

    Per default, this iterates through all the source files and creates (or
    updates) file metadata json files.

    At the end, dataset statistics and documents.csv (and their diff) are
    created.

    Args:
        dataset: leakrfc Dataset instance
        use_cache: Use global processing cache to skip tasks
        check_integrity: Check checksum for each file (logs mismatches)
        cleanup: When checking integrity, fix mismatched metadata and delete
            unreferenced metadata files
        metadata_only: Only iterate through existing metadata files, don't look
            for new source files

    """
    worker = MakeWorker(
        check_integrity, cleanup, metadata_only, dataset, use_cache=use_cache
    )
    return worker.run()

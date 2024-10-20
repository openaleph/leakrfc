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
from leakrfc.worker import DatasetWorker


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


def make_cache_key(self: "LeakrfcWorker", task: Task) -> str | None:
    if self.use_cache:
        key, action = task
        return f"{self.dataset.name}/make/{action}/{key}"


def make_cache_key_integrity(self: "LeakrfcWorker", key: str) -> str | None:
    if self.use_cache:
        return f"{self.dataset.name}/make/integrity/{key}"


class LeakrfcWorker(DatasetWorker):
    def __init__(
        self,
        check_integrity: bool | None = True,
        cleanup: bool | None = True,
        *args,
        **kwargs,
    ) -> None:
        kwargs["status_model"] = kwargs.get("status_model", MakeStatus)
        super().__init__(*args, **kwargs)
        self.check_integrity = check_integrity
        self.cleanup = cleanup

    def get_tasks(self) -> Generator[Task, None, None]:
        self.log_info("Checking source files ...")
        for key in self.dataset.iter_keys():
            self.count(files_total=1)
            yield key, ACTION_SOURCE
        self.log_info("Checking existing files ...")
        for file in super().get_tasks():
            self.count(metadata_total=1)
            yield file.key, ACTION_INFO

    @anycache(store=get_cache(), key_func=make_cache_key)
    def handle_task(self, task: Task) -> str:
        key, action = task
        now = datetime.now().isoformat()
        if action == ACTION_SOURCE:
            self.log_info(f"Checking `{key}` ...", action=action)
            if not self.dataset.exists(key):
                self.dataset.archive_file(key, self.dataset._storage)
                self.count(files_added=1)
            self._ensure_integrity(key)
        elif action == ACTION_INFO:
            self.log_info(f"Checking `{key}` metadata ...", action=action)
            self._ensure_integrity(key)
        return now

    @anycache(store=get_cache(), key_func=make_cache_key_integrity)
    def _ensure_integrity(self, key: str) -> None:
        if self.check_integrity:
            self.count(files_checked=1)
            self.log_info(f"Testing checksum for `{key}` ...")
            try:
                content_hash = self.dataset.make_checksum(key)
                file = self.dataset.lookup_file(key)
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
            except DoesNotExist:
                self.log_error(f"Source file `{key}` does not exist")
                self.count(files_deleted=1)
                if self.cleanup:
                    self.log_info(f"Deleting metadata for `{key}` ...")
                    self.dataset.delete_file(key)


def make_dataset(
    dataset: DatasetArchive,
    use_cache: bool | None = True,
    check_integrity: bool | None = True,
    cleanup: bool | None = True,
) -> MakeStatus:
    worker = LeakrfcWorker(check_integrity, cleanup, dataset, use_cache=use_cache)
    return worker.run()

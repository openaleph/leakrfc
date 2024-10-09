"""
Make or update a leakrfc dataset and check integrity
"""

from datetime import datetime
from typing import Generator, Literal, TypeAlias

from anystore.exceptions import DoesNotExist
from anystore.store import MemoryStore
from pydantic import BaseModel

from leakrfc.archive.dataset import DatasetArchive
from leakrfc.worker import DatasetWorker


class MakeResult(BaseModel):
    files_total: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    integrity_errors: int = 0


class Options(BaseModel):
    check_integrity: bool | None = True
    cleanup: bool | None = True


ACTION_SOURCE = "source"
ACTION_INFO = "info"
Action: TypeAlias = Literal["info", "source"]
Task: TypeAlias = tuple[str, Action]


class LeakrfcWorker(DatasetWorker):
    def __init__(self, options: Options, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.run_cache = MemoryStore()
        self.options = options
        self.result = MakeResult()

    def get_tasks(self) -> Generator[Task, None, None]:
        self.log_info("Checking source files ...")
        for key in self.dataset._storage.iterate_keys(
            exclude_prefix=self.dataset.metadata_prefix
        ):
            yield key, ACTION_SOURCE
        self.log_info("Checking source files ...")
        for file in super().get_tasks():
            yield file.key, ACTION_INFO

    def handle_task(self, task: Task) -> str:
        key, action = task
        now = datetime.now().isoformat()
        if action == ACTION_SOURCE:
            self.log_info(f"Checking `{key}` ...", action=action)
            if not self.dataset.exists(key):
                self.dataset.archive_file(key, self.dataset._storage)
                self._set_integrity(key, True)
                self.result.files_added += 1
            self._ensure_integrity(key)
            self.result.files_total += 1
        elif action == ACTION_INFO:
            self.log_info(f"Checking `{key}` metadata ...", action=action)
            self._ensure_integrity(key)
        return now

    def _ensure_integrity(self, key: str) -> None:
        if self.options.check_integrity:
            if self._get_integrity(key) is None:
                self.log_info(f"Testing checksum for `{key}` ...")
                try:
                    content_hash = self.dataset._storage.checksum(key)
                    file = self.dataset.lookup_file(key)
                    if content_hash == file.content_hash:
                        self._set_integrity(key, True)
                    else:
                        self.log_error(
                            f"Checksum mismatch for `{key}`: `{content_hash}`",
                            file=file,
                        )
                        self._set_integrity(key, False)
                        self.result.integrity_errors += 1
                        if self.options.cleanup:
                            self.log_info(f"Fixing checksum for `{key}` ...")
                            file.content_hash = content_hash
                            self.dataset._put_file_info(file)
                except DoesNotExist:
                    self.log_error(f"Source file `{key}` does not exist")
                    self._set_integrity(key, False)
                    self.result.files_deleted += 1
                    if self.options.cleanup:
                        self.log_info(f"Deleting metadata for `{key}` ...")
                        self.dataset.delete_file(key)

    def _set_integrity(self, key, value: bool) -> None:
        self.run_cache.put(f"integrity/{key}", int(value))

    def _get_integrity(self, key) -> bool | None:
        return self.run_cache.get(f"integrity/{key}", raise_on_nonexist=False)


def make_dataset(dataset: DatasetArchive, **kwargs) -> MakeResult:
    options = Options(**kwargs)
    worker = LeakrfcWorker(options, dataset)
    worker.run()
    return worker.result

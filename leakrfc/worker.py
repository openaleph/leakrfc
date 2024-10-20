from typing import Any

from anystore.worker import Worker

from leakrfc.archive.dataset import DatasetArchive
from leakrfc.logging import get_logger
from leakrfc.settings import Settings

log = get_logger(__name__)

settings = Settings()


class DatasetWorker(Worker):
    def __init__(
        self, dataset: DatasetArchive, use_cache: bool | None = True, *args, **kwargs
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

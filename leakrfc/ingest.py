import os
import tempfile
from os import PathLike
from pathlib import Path
from typing import Any

import shortuuid
from anystore import get_store as get_file_store
from followthemoney import model
from followthemoney.proxy import EntityProxy
from ftmq.store import get_store as get_ftm_store
from ftmq.util import make_proxy
from ingestors.manager import Manager

from leakrfc.archive.dataset import DatasetArchive
from leakrfc.logging import get_logger
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


class IngestManager(Manager):
    def __init__(
        self,
        dataset: DatasetArchive,
        worker: DatasetWorker,
        context: dict[str, Any] | None = None,
    ):
        store = get_ftm_store()
        self.writer = store.writer()
        self.dataset = dataset
        self.context = context
        self.work_path = Path(tempfile.mkdtemp(prefix="leakrfc-ingestor-"))
        self.work_store = get_file_store(self.work_path)
        self.emitted = set()
        self.worker = worker

    @property
    def archive(self):
        raise NotImplementedError("Accessing archive not implemented")

    def make_entity(self, schema: str, parent=None) -> EntityProxy:
        entity = model.make_entity(schema)
        self.make_child(parent, entity)
        return entity

    def emit_entity(self, entity: EntityProxy, *args, **kwargs):
        entity = make_proxy(entity.to_dict(), dataset=self.dataset.name)
        self.writer.add_entity(entity)
        self.emitted.add(entity.id)

    def queue_entity(self, entity: EntityProxy):
        self.worker.queue.put(entity.to_full_dict())

    def store(self, file_path: PathLike, *args, **kwargs) -> str:
        file = self.dataset.archive_file(file_path)
        return file.content_hash

    def load(self, content_hash: str, file_name: str | None = None) -> Path:
        file_name = file_name or shortuuid.uuid()
        path = os.path.join(content_hash, file_name)
        with self.dataset.open_file(content_hash) as i:
            with self.work_store.open(path, mode="wb") as o:
                o.write(i.read())
        return (self.work_path / path).resolve().absolute()


class IngestWorker(DatasetWorker):
    def get_tasks(self) -> Any:
        for file in super().get_tasks():
            yield file.to_proxy().to_full_dict()

    def handle_task(self, task: dict[str, Any]) -> None:
        entity = model.get_proxy(task)
        manager = IngestManager(self.dataset, self)
        log.debug("Ingest: %r", entity)
        try:
            manager.ingest_entity(entity)
        finally:
            manager.close()
        log.debug("Created %d entities", len(manager.emitted))


def ingest_dataset(dataset: DatasetArchive) -> None:
    worker = IngestWorker(dataset)
    worker.log_info(f"Ingesting dataset `{dataset.name}` ...")
    worker.run()

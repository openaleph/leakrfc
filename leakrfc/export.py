from anystore.store import ZipStore
from anystore.types import StrGenerator, Uri
from anystore.worker import WorkerStatus
from fsspec.implementations.zip import zipfile

from leakrfc.archive import DatasetArchive
from leakrfc.logging import get_logger
from leakrfc.worker import DatasetWorker

log = get_logger(__name__)


class ExportWorker(DatasetWorker):
    def __init__(self, out: ZipStore, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.out = out
        self.consumer_threads = 1

    def get_tasks(self) -> StrGenerator:
        yield from self.dataset._storage.iterate_keys()

    def handle_task(self, task: str) -> None:
        self.log_info(f"Adding file `{task}` ...")
        with self.dataset._storage.open(task) as i:
            with self.out.open(f"{self.dataset.name}/{task}", mode="wb") as o:
                o.write(i.read())

    def done(self) -> None:
        self.log_info(f"Exporting dataset `{self.dataset.name}`: Done.")


def export_dataset(dataset: DatasetArchive, uri: Uri) -> WorkerStatus:
    out = ZipStore(uri=uri, backend_config={"compression": zipfile.ZIP_LZMA})
    worker = ExportWorker(out, dataset)
    worker.log_info(f"Exporting dataset `{dataset.name}` ...")
    return worker.run()

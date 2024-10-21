"""
Sync Aleph collections into leakrfc or vice versa via `alephclient`
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from anystore import anycache
from anystore.store.virtual import get_virtual
from anystore.worker import WorkerStatus

from leakrfc.archive.cache import get_cache
from leakrfc.archive.dataset import DatasetArchive
from leakrfc.connectors import aleph
from leakrfc.model import OriginalFile
from leakrfc.worker import DatasetWorker


def _make_cache_key(self: "AlephUploadWorker", *parts: str) -> str:
    host = urlparse(self.host).netloc
    base = f"aleph/upload/{host}/{self.dataset.name}/"
    return base + "/".join(parts)


def get_upload_cache_key(self: "AlephUploadWorker", file: OriginalFile) -> str | None:
    if self.use_cache:
        return _make_cache_key(self, file.key)


def get_parent_cache_key(
    self: "AlephUploadWorker", key: str, prefix: str | None = None
) -> str | None:
    if self.use_cache:
        parts = [str(Path(key).parent)]
        if prefix:
            parts += prefix
        return _make_cache_key(self, *parts)


class AlephUploadStatus(WorkerStatus):
    added: int = 0
    folders_created: int = 0


class AlephUploadWorker(DatasetWorker):
    """
    Sync leakrfc dataset to an Aleph instance
    """

    def __init__(
        self,
        host: str | None = None,
        api_key: str | None = None,
        prefix: str | None = None,
        foreign_id: str | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tmp = get_virtual(f"leakrfc-{self.dataset.name}-")
        self.api = aleph.get_api(host, api_key)
        self.host = aleph.get_host(self.api)
        self.foreign_id = foreign_id or self.dataset.name
        self.collection_id = aleph.get_or_create_collection_id(
            self.foreign_id, self.api
        )
        self.prefix = prefix
        self.consumer_threads = min(10, self.consumer_threads)  # urllib connection pool

    @anycache(store=get_cache(), key_func=get_parent_cache_key)
    def get_parent(self, key: str, prefix: str | None = None) -> dict[str, str] | None:
        with self.lock:
            p = Path(key)
            if prefix:
                p = prefix / p
            parent_path = str(p.parent)
            if not parent_path or parent_path == ".":
                return
            parent = {"id": aleph.make_folders(parent_path, self.collection_id)}
            self.count(folders_created=1)
            return parent

    @anycache(store=get_cache(), key_func=get_upload_cache_key)
    def handle_task(self, task: OriginalFile) -> dict[str, Any]:
        res = {
            "uploaded_at": datetime.now().isoformat(),
            "dataset": self.dataset.name,
            "host": self.host,
        }
        self.log_info(
            f"Uploading `{task.key}` ({task.content_hash}) ...",
            aleph=self.host,
            foreign_id=self.foreign_id,
        )
        metadata = {**task.extra, "file_name": task.name, "foreign_id": task.key}
        metadata["source_url"] = metadata.get("url")
        parent = self.get_parent(task.key, self.prefix)
        if parent:
            metadata["parent"] = parent
        tmp_key = self.tmp.download(
            self.dataset._make_path(task.key), self.dataset._storage
        )
        tmp_path = urlparse(self.tmp.store.get_key(tmp_key)).path
        res.update(
            self.api.ingest_upload(
                self.collection_id, Path(tmp_path), metadata=metadata
            )
        )
        self.tmp.cleanup(tmp_key)
        self.log_info(
            f"Upload complete. Aleph id: `{res['id']}`",
            content_hash=task.content_hash,
            aleph=self.host,
            file=task.key,
            foreign_id=self.foreign_id,
        )
        self.count(uploaded=1)
        return res

    def done(self) -> None:
        self.tmp.cleanup()
        self.log_info("Syncing to Aleph: Done")


def sync_to_aleph(
    dataset: DatasetArchive,
    host: str | None,
    api_key: str | None,
    prefix: str | None = None,
    foreign_id: str | None = None,
    use_cache: bool | None = True,
) -> AlephUploadStatus:
    worker = AlephUploadWorker(
        dataset=dataset,
        host=host,
        api_key=api_key,
        prefix=prefix,
        foreign_id=foreign_id,
        use_cache=use_cache,
    )
    worker.log_info(f"Starting sync to Aleph `{worker.host}` ...")
    return worker.run()

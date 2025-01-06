"""
Sync Aleph collections into leakrfc or vice versa via `alephclient`
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from anystore import anycache
from anystore.worker import WorkerStatus

from leakrfc.archive.cache import get_cache
from leakrfc.archive.dataset import DatasetArchive
from leakrfc.connectors import aleph
from leakrfc.model import File
from leakrfc.worker import DatasetWorker, make_cache_key


def _make_cache_key(self: "AlephUploadWorker", *parts: str) -> str:
    host = urlparse(self.host).netloc
    assert host is not None
    return make_cache_key(self, "sync", "aleph", host, *parts)


def get_upload_cache_key(self: "AlephUploadWorker", file: File) -> str | None:
    return _make_cache_key(self, file.key)


def get_parent_cache_key(
    self: "AlephUploadWorker", key: str, prefix: str | None = None
) -> str | None:
    parts = [str(Path(key).parent)]
    if prefix:
        parts += prefix
    return _make_cache_key(self, *parts)


def get_version_cache_key(self: "AlephUploadWorker", version: str) -> str | None:
    return _make_cache_key(self, "versions", version)


def get_current_version_cache_key(self: "AlephUploadWorker") -> str:
    return self.dataset.documents.get_current_version()


class AlephUploadStatus(WorkerStatus):
    uploaded: int = 0
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
        metadata: bool | None = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.api = aleph.get_api(host, api_key)
        self.host = aleph.get_host(self.api)
        self.foreign_id = foreign_id or self.dataset.name
        self.collection_id = aleph.get_or_create_collection_id(
            self.foreign_id, self.api
        )
        self.prefix = prefix
        self.consumer_threads = min(10, self.consumer_threads)  # urllib pool limit

        if metadata:
            self.log_info(
                "Updating collection metadata ...",
                aleph=self.host,
                foreign_id=self.foreign_id,
            )
            aleph.update_collection_metadata(self.dataset.name, self.dataset.config)

    def get_tasks(self) -> Any:
        for version in self.get_versions():
            self.queue_tasks_from_version(version)
        yield

    @anycache(store=get_cache(), key_func=get_current_version_cache_key)
    def get_versions(self) -> list[str]:
        return self.dataset.documents.get_versions()

    @anycache(store=get_cache(), key_func=get_version_cache_key)
    def queue_tasks_from_version(self, version: str) -> datetime:
        now = datetime.now()
        for key in self.dataset.documents.get_keys_added(version):
            self.queue_task(self.dataset.lookup_file(key))
        return now

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
    def handle_task(self, task: File) -> dict[str, Any]:
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
        with self.local_file(task.key, self.dataset._storage) as file:
            tmp_path = urlparse(file.uri).path
            res.update(
                self.api.ingest_upload(
                    self.collection_id, Path(tmp_path), metadata=metadata
                )
            )
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
        self.log_info("Syncing to Aleph: Done")


def sync_to_aleph(
    dataset: DatasetArchive,
    host: str | None,
    api_key: str | None,
    prefix: str | None = None,
    foreign_id: str | None = None,
    use_cache: bool | None = True,
    metadata: bool | None = True,
) -> AlephUploadStatus:
    worker = AlephUploadWorker(
        dataset=dataset,
        host=host,
        api_key=api_key,
        prefix=prefix,
        foreign_id=foreign_id,
        use_cache=use_cache,
        metadata=metadata,
    )
    worker.log_info(f"Starting sync to Aleph `{worker.host}` ...")
    return worker.run()

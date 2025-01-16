"""
Sync Aleph collections into leakrfc or vice versa via `alephclient`
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from anystore import anycache
from anystore.io import logged_items
from anystore.worker import WorkerStatus

from leakrfc.archive.cache import get_cache
from leakrfc.archive.dataset import DatasetArchive
from leakrfc.connectors import aleph
from leakrfc.model import File


def make_upload_cache_key(self: "AlephUploadWorker", file: File) -> str | None:
    return aleph.make_aleph_cache_key(self, file.key)


def make_parent_cache_key(
    self: "AlephUploadWorker", key: str, prefix: str | None = None
) -> str | None:
    parts = [str(Path(key).parent)]
    if prefix:
        parts = [prefix] + parts
    return aleph.make_aleph_cache_key(self, "folder", *parts, "created")


def make_version_cache_key(self: "AlephUploadWorker", version: str) -> str | None:
    return aleph.make_aleph_cache_key(self, "versions", version)


def make_current_version_cache_key(self: "AlephUploadWorker") -> str:
    version = self.dataset.documents.get_current_version()
    return aleph.make_aleph_cache_key(self, version)


class AlephUploadStatus(WorkerStatus):
    uploaded: int = 0
    folders_created: int = 0


class AlephUploadWorker(aleph.AlephDatasetWorker):
    def __init__(self, prefix: str | None = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.prefix = prefix
        self.status_model = AlephUploadStatus

        if self.update_metadata:
            self.log_info(
                "Updating collection metadata ...",
                aleph=self.host,
                foreign_id=self.foreign_id,
            )
            aleph.update_collection_metadata(self.foreign_id, self.dataset.config)

    def get_tasks(self) -> Any:
        for version in self.get_versions():
            self.queue_tasks_from_version(version)
        return []

    @anycache(store=get_cache(), key_func=make_current_version_cache_key)
    def get_versions(self) -> list[str]:
        return self.dataset.documents.get_versions()

    @anycache(store=get_cache(), key_func=make_version_cache_key)
    def queue_tasks_from_version(self, version: str) -> datetime:
        self.log_info("Loading documents diff ...", version=version)
        now = datetime.now()
        for key in logged_items(
            self.dataset.documents.get_keys_added(version),
            version=version,
            action="Load",
            item_name="Document",
        ):
            self.queue_task(self.dataset.lookup_file(key))
        return now

    @anycache(store=get_cache(), key_func=make_parent_cache_key)
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

    @anycache(store=get_cache(), key_func=make_upload_cache_key)
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


def sync_to_aleph(
    dataset: DatasetArchive,
    host: str | None,
    api_key: str | None,
    prefix: str | None = None,
    foreign_id: str | None = None,
    use_cache: bool | None = True,
    metadata: bool | None = True,
) -> AlephUploadStatus:
    """
    Incrementally sync a leakrfc dataset into an Aleph instance.

    As long as using `use_cache`, only new documents will be imported.

    Args:
        dataset: leakrfc Dataset instance
        host: Aleph host (can be set via env `ALEPHCLIENT_HOST`)
        api_key: Aleph api key (can be set via env `ALEPHCLIENT_API_KEY`)
        prefix: Add a folder prefix to import documents into
        foreign_id: Aleph collection foreign_id (if different from leakrfc dataset name)
        use_cache: Use global processing cache to skip tasks
        metadata: Update Aleph collection metadata
    """
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

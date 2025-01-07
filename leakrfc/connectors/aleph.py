import os
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from alephclient.api import AlephAPI
from alephclient.errors import AlephException
from alephclient.settings import API_KEY, HOST
from anystore.util import clean_dict
from banal import ensure_list

from leakrfc.logging import get_logger
from leakrfc.model import DatasetModel
from leakrfc.worker import DatasetWorker, make_cache_key

log = get_logger(__name__)


@cache
def get_api(host: str | None = None, api_key: str | None = None) -> AlephAPI:
    return AlephAPI(host=host or HOST, api_key=api_key or API_KEY)


@cache
def get_host(api: AlephAPI | None = None) -> str:
    api = api or get_api()
    return api.base_url[:-7]


@cache
def get_foreign_id(collection_id: str, api: AlephAPI | None = None) -> str:
    api = api or get_api()
    res = api.get_collection(collection_id)
    if res is None:
        raise AlephException(
            "Collection with collection_id `%s` not found or not accessible."
            % collection_id
        )
    return res["foreign_id"]


@cache
def get_collection_id(foreign_id: str, api: AlephAPI | None = None) -> str:
    api = api or get_api()
    res = api.get_collection_by_foreign_id(foreign_id)
    if res is None:
        raise AlephException(
            "Collection with foreign_id `%s` not found or not accessible." % foreign_id
        )
    return res["id"]


@cache
def get_or_create_collection_id(foreign_id: str, api: AlephAPI | None = None) -> str:
    api = api or get_api()
    res = api.load_collection_by_foreign_id(foreign_id)
    return res["id"]


@cache
def make_folders(path: str, collection_id: str, parent: str | None = None) -> str:
    api = get_api()
    log.info(f"Creating folder: `{path}`", host=get_host(api))
    folder = Path(path)
    foreign_id = "/".join(folder.parts)  # same as alephclient
    if len(folder.parts) > 1:
        parent = make_folders(os.path.join(*folder.parts[:-1]), collection_id, parent)
    metadata: dict[str, Any] = {"file_name": folder.name, "foreign_id": foreign_id}
    if parent is not None:
        metadata["parent"] = {"id": parent}
    res = api.ingest_upload(collection_id, metadata=metadata)
    return res["id"]


def update_collection_metadata(
    foreign_id: str, dataset: DatasetModel
) -> dict[str, Any]:
    data = clean_dict(dataset.model_dump(mode="json"))
    publisher = {}
    if dataset.publisher:
        publisher = clean_dict(dataset.publisher.model_dump(mode="json"))
    description = data.get("description") or ""
    summary = data.get("summary") or ""
    summary = (description + "\n\n" + summary).strip()
    data = {
        "label": dataset.title,
        "summary": summary,
        "publisher": publisher.get("name"),
        "publisher_url": publisher.get("url"),
        "countries": ensure_list(publisher.get("country")),
        "data_url": data.get("data_url"),
        "category": data.get("category") or "other",
    }
    if dataset.coverage and dataset.coverage.frequency:
        data["frequency"] = dataset.coverage.frequency
    collection_id = get_or_create_collection_id(foreign_id)
    api = get_api()
    return api.update_collection(collection_id, data)


class AlephDatasetWorker(DatasetWorker):
    """Base worker for aleph related things"""

    def __init__(
        self,
        host: str | None = None,
        api_key: str | None = None,
        foreign_id: str | None = None,
        metadata: bool | None = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.api = get_api(host, api_key)
        self.host = get_host(self.api)
        self.foreign_id = foreign_id or self.dataset.name
        self.collection_id = get_or_create_collection_id(self.foreign_id, self.api)
        self.update_metadata = metadata
        self.consumer_threads = min(10, self.consumer_threads)  # urllib pool limit

    def done(self) -> None:
        self.log_info("Syncing to Aleph: Done", host=self.host)


def make_aleph_cache_key(self: AlephDatasetWorker, *parts: str) -> str:
    host = urlparse(self.host).netloc
    assert host is not None
    return make_cache_key(self, "sync", "aleph", host, *parts)

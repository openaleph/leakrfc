"""
Sync followthemoney entities into Aleph instances

This is a bit off from the other lekrfc dataset logic but needs a place somewhere.
"""

from datetime import datetime
from fnmatch import fnmatch
from typing import Any, Generator

from anystore import anycache
from anystore.worker import WorkerStatus
from ftmq.io import smart_read_proxies
from ftmq.model import Catalog, Dataset, Resource
from rigour.mime.types import FTM

from leakrfc.archive import get_dataset
from leakrfc.archive.cache import get_cache
from leakrfc.connectors.aleph import (
    AlephDatasetWorker,
    make_aleph_cache_key,
    update_collection_metadata,
)


def make_resource_cache_key(self, resource: Resource) -> str | None:
    key = resource.checksum or resource.timestamp
    if key:
        return make_aleph_cache_key(self, "resource", str(key))


class AlephLoadDatasetStatus(WorkerStatus):
    resources: int = 0
    entities: int = 0


class AlephLoadDataset(AlephDatasetWorker):
    """
    Incrementally write followthemoney entities to an Aleph instance following
    the dataset/catalog spec by `nomenklatura`. This caches resources that
    already have been imported.
    """

    def __init__(self, index_uri: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.index_uri = index_uri
        self.status_model = AlephLoadDatasetStatus

        if self.update_metadata:
            dataset = Dataset._from_uri(self.index_uri)
            self.log_info(
                "Updating collection metadata ...",
                aleph=self.host,
                foreign_id=self.foreign_id,
            )
            update_collection_metadata(self.foreign_id, dataset)

    @anycache(store=get_cache(), key_func=make_resource_cache_key)
    def queue_tasks_from_resource(self, resource: Resource) -> datetime:
        now = datetime.now()
        buffer = []
        ix = 1
        for ix, proxy in enumerate(
            smart_read_proxies(resource.url, serialize=False), 1
        ):
            buffer.append(proxy)
            if ix % 1000 == 0:
                self.log_info(f"Loading {ix} entities ...", resource=str(resource.url))
                self.queue_task(buffer)
                self.count(entities=len(buffer))
                buffer = []
        self.queue_task(buffer)
        self.count(entities=len(buffer), resources=1)
        buffer = []
        self.log_info(f"Loaded {ix} entities.", resource=str(resource.url))
        return now

    def handle_task(self, task: Any) -> Any:
        self.api.write_entities(self.collection_id, task)
        self.log_info(f"Write {len(task)} entities to Aleph.", host=self.host)

    def get_tasks(self) -> Any:
        dataset = Dataset._from_uri(self.index_uri)
        for resource in dataset.resources:
            if resource.mime_type == FTM:
                self.queue_tasks_from_resource(resource)
        return []


def load_dataset(
    uri: str,
    host: str | None,
    api_key: str | None,
    foreign_id: str | None = None,
    use_cache: bool | None = True,
    metadata: bool | None = True,
) -> AlephLoadDatasetStatus:
    dataset = Dataset._from_uri(uri)
    dataset = get_dataset(dataset.name)
    worker = AlephLoadDataset(
        uri,
        dataset=dataset,
        host=host,
        api_key=api_key,
        foreign_id=foreign_id,
        use_cache=use_cache,
        metadata=metadata,
    )
    res = worker.run()
    return res


def load_catalog(
    uri: str,
    host: str | None,
    api_key: str | None,
    foreign_id: str | None = None,
    use_cache: bool | None = True,
    metadata: bool | None = True,
    exclude_dataset: str | None = None,
    include_dataset: str | None = None,
) -> Generator[AlephLoadDatasetStatus, None, None]:
    catalog = Catalog._from_uri(uri)
    for dataset in catalog.datasets:
        if exclude_dataset and fnmatch(dataset.name, exclude_dataset):
            continue
        if include_dataset and not fnmatch(dataset.name, include_dataset):
            continue

        yield load_dataset(
            dataset.index_url or dataset.uri,
            host=host,
            api_key=api_key,
            foreign_id=foreign_id,
            use_cache=use_cache,
            metadata=metadata,
        )

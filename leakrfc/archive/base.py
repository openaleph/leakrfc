import os
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import fsspec
import yaml
from anystore import get_store as _get_store
from anystore.store import Store, ZipStore
from ftmq.model import Catalog, Dataset

from leakrfc.logging import get_logger
from leakrfc.model import ArchiveModel

if TYPE_CHECKING:
    from leakrfc.archive.dataset import DatasetArchive


log = get_logger(__name__)


OPTS = {"serialization_mode": "raw"}


def get_store(**kwargs) -> Store | ZipStore:
    uri = kwargs.get("uri")
    if uri and os.path.splitext(uri)[1] == ".leakrfc":
        return ZipStore(**kwargs)
    return _get_store(**kwargs)


class BaseArchive(ArchiveModel):
    @cached_property
    def _storage(self) -> Store:
        if self.storage is not None:
            config = {**self.storage.model_dump(), **OPTS}
            return get_store(**config)
        return get_store(uri=self.uri, **OPTS)

    @cached_property
    def is_zip(self) -> bool:
        return isinstance(self._storage, ZipStore)

    def _make_path(self, *parts: str) -> str:
        return "/".join([p.strip("/") for p in parts if p.strip("/")])


class Archive(BaseArchive):
    """
    Leakrfc archive that holds one or more datasets as subdirs
    """

    def get_dataset(self, dataset: str) -> "DatasetArchive":
        from leakrfc.archive.dataset import DatasetArchive

        config_uri = f"{dataset}/{self.metadata_prefix}/config.yml"
        config = {}
        if self._storage.exists(config_uri):
            config = self._storage.get(config_uri, deserialization_func=yaml.safe_load)
        if "storage" not in config:
            storage = self._storage.model_dump()
            if not self.is_zip:
                storage["uri"] = self._make_path(self._storage.uri, dataset)
            config.update(storage=storage)
        config["name"] = dataset
        return DatasetArchive(**config)

    def get_datasets(self) -> Generator["DatasetArchive", None, None]:
        fs, _ = fsspec.url_to_fs(str(self._storage.uri))
        for child in fs.ls(self._storage.uri):
            dataset = Path(child).name
            if self._storage.exists(f"{dataset}/{self.metadata_prefix}"):
                yield self.get_dataset(dataset)

    def make_catalog(self, collect_stats: bool | None = False) -> Catalog:
        datasets = []
        for dataset in self.get_datasets():
            ds = Dataset(
                name=dataset.name,
                from_uri=dataset.make_index(collect_stats=collect_stats),
            )
            datasets.append(ds)
        return Catalog(**self.model_dump(), datasets=datasets)

import os
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import fsspec
import yaml
from anystore import get_store as _get_store
from anystore.store import Store, ZipStore
from anystore.store.base import BaseStore

from leakrfc.logging import get_logger
from leakrfc.model import ArchiveModel, default_cache

if TYPE_CHECKING:
    from leakrfc.archive.dataset import DatasetArchive, ReadOnlyDatasetArchive


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
        if self.storage_config is not None:
            config = {**self.storage_config.model_dump(), **OPTS}
            return get_store(**config)
        return get_store(self.uri, **OPTS)

    def _make_path(self, *parts: str) -> str:
        return "/".join([p.strip("/") for p in parts if p.strip("/")])


class Archive(BaseArchive):
    """
    Leakrfc archive that holds one or more datasets as subdirs
    """

    @cached_property
    def cache(self) -> BaseStore:
        if self.cache_config is not None:
            return get_store(**self.cache_config.model_dump())
        return default_cache

    def get_dataset(self, dataset: str) -> "DatasetArchive | ReadOnlyDatasetArchive":
        from leakrfc.archive.dataset import DatasetArchive, ReadOnlyDatasetArchive

        config_uri = f"{dataset}/{self.metadata_prefix}/config.yml"
        config = {"storage_config": self._storage.model_dump()}
        if self._storage.exists(config_uri):
            config.update(
                **self._storage.get(config_uri, deserialization_func=yaml.safe_load)
            )
        config["name"] = dataset
        config["archive"] = self
        if config["storage_config"].get("readonly"):
            return ReadOnlyDatasetArchive(**config)
        return DatasetArchive(**config)

    def get_datasets(
        self,
    ) -> Generator["DatasetArchive | ReadOnlyDatasetArchive", None, None]:
        fs, _ = fsspec.url_to_fs(str(self._storage.uri))
        for child in fs.ls(self._storage.uri):
            dataset = Path(child).name
            if self._storage.exists(f"{dataset}/{self.metadata_prefix}"):
                yield self.get_dataset(dataset)

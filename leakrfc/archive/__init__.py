import os
from functools import lru_cache

from anystore.model import StoreModel
from anystore.types import Uri
from anystore.util import ensure_uri

from leakrfc.archive.base import Archive
from leakrfc.archive.dataset import DatasetArchive, ReadOnlyDatasetArchive


def configure_archive(**kwargs) -> Archive:
    """change config during tests runtime"""
    from leakrfc.settings import ArchiveSettings

    settings = ArchiveSettings()
    if settings.uri is not None:
        return get_archive(settings.uri)
    return Archive(**{**settings.model_dump(), **kwargs})


@lru_cache(1024)
def get_archive(uri: Uri | None = None, **kwargs) -> Archive:
    if uri is not None:
        uri = ensure_uri(uri)
        ext = os.path.splitext(uri)[1]
        if ext in (".yml", ".yaml"):
            return Archive._from_uri(uri, **kwargs)
        else:
            return Archive(storage=StoreModel(uri=uri, **kwargs))
    return configure_archive()


@lru_cache(1024)
def get_dataset(
    dataset: str, uri: Uri | None = None, **kwargs
) -> DatasetArchive | ReadOnlyDatasetArchive:
    if uri is not None:
        return DatasetArchive(name=dataset, uri=str(uri), **kwargs)
    archive = get_archive(**kwargs)
    return archive.get_dataset(dataset)


archive = get_archive()

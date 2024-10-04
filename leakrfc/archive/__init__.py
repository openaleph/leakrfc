import os
from functools import cache

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


@cache
def get_archive(uri: Uri | None = None) -> Archive:
    if uri is not None:
        uri = ensure_uri(uri)
        ext = os.path.splitext(uri)[1]
        if ext in (".yml", ".yaml"):
            return Archive._from_uri(uri)
        else:
            return Archive(storage_config=StoreModel(uri=uri))
    return configure_archive()


@cache
def get_dataset(
    dataset: str, **archive_kwargs
) -> DatasetArchive | ReadOnlyDatasetArchive:
    archive = get_archive(**archive_kwargs)
    return archive.get_dataset(dataset)


archive = get_archive()

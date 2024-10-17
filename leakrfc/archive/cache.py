from functools import cache

from anystore import get_store
from anystore.store import BaseStore

from leakrfc.logging import get_logger

log = get_logger(__name__)


@cache
def get_cache() -> BaseStore:
    from leakrfc.settings import ArchiveSettings

    settings = ArchiveSettings()
    if settings.cache is not None:
        return get_store(**settings.cache.model_dump())
    log.warning(
        "Using in-memory cache. This is not for production use! "
        "Configure via env `LEAKRFC_CACHE__*`"
    )
    return get_store("memory:///")

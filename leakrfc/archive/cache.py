from functools import cache

from anystore import get_store
from anystore.store import BaseStore

from leakrfc.logging import configure_logging, get_logger

log = get_logger(__name__)


@cache
def get_cache() -> BaseStore:
    from leakrfc.settings import ArchiveSettings

    settings = ArchiveSettings()
    if settings.cache is not None:
        return get_store(**settings.cache.model_dump())
    configure_logging(logger=__name__)
    log.warning(
        "Using in-memory cache. Consider configuring properly via env "
        "`LEAKRFC_CACHE__*` for persistent production use."
    )
    return get_store("memory:///")

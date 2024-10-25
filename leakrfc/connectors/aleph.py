import os
from functools import cache
from pathlib import Path
from typing import Any

from alephclient.api import AlephAPI
from alephclient.settings import API_KEY, HOST

from leakrfc.logging import get_logger

log = get_logger(__name__)


class AlephException(BaseException):
    pass


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
    foreign_id = "/".join(folder.parts)
    if len(folder.parts) > 1:
        parent = make_folders(os.path.join(*folder.parts[:-1]), collection_id, parent)
    metadata: dict[str, Any] = {"file_name": folder.name, "foreign_id": foreign_id}
    if parent is not None:
        metadata["parent"] = {"id": parent}
    res = api.ingest_upload(collection_id, metadata=metadata)
    return res["id"]

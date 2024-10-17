from anystore import anycache
from anystore.store.fs import DoesNotExist
from anystore.util import clean_dict
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from leakrfc import __version__
from leakrfc.archive import archive
from leakrfc.archive.cache import get_cache
from leakrfc.logging import get_logger
from leakrfc.model import File
from leakrfc.settings import Settings

settings = Settings()
log = get_logger(__name__)
DEFAULT_ERROR = HTTPException(404)
BASE_HEADER = {"x-leakrfc-version": __version__}


def get_base_header(dataset: str, key: str | None = None) -> dict[str, str]:
    return clean_dict(
        {**BASE_HEADER, "x-leakrfc-dataset": dataset, "x-leakrfc-key": key}
    )


def get_file_header(file: File) -> dict[str, str]:
    return clean_dict(
        {
            **get_base_header(file.dataset, file.content_hash),
            "x-leakrfc-file": file.name,
            "x-leakrfc-size": str(file.size),
            "x-mimetype": file.mimetype,
            "content-type": file.mimetype,
        }
    )


class Context(BaseModel):
    dataset: str
    key: str
    file: File

    @property
    def headers(self) -> dict[str, str]:
        return get_file_header(self.file)


class Errors:
    def __enter__(self):
        pass

    def __exit__(self, exc_cls, exc, _):
        if exc_cls is not None:
            log.error(f"{exc_cls.__name__}: `{exc}`")
            if not settings.debug:
                # always just 404 for information hiding
                raise DEFAULT_ERROR
            else:
                if exc_cls == DoesNotExist:
                    raise DEFAULT_ERROR
                raise exc


@anycache(store=get_cache(), key_func=lambda d, k: f"api/file/{d}/{k}", model=File)
def get_file_info(dataset: str, key: str) -> File | None:
    storage = archive.get_dataset(dataset)
    return storage.lookup_file_by_hash(key)


def ensure_path_context(dataset: str, key: str) -> Context:
    with Errors():
        return Context(dataset=dataset, key=key, file=get_file_info(dataset, key))


def stream_file(ctx: Context) -> StreamingResponse:
    storage = archive.get_dataset(ctx.dataset)
    file = storage.lookup_file_by_hash(ctx.key)
    return StreamingResponse(
        storage.stream_file(file),
        headers=ctx.headers,
        media_type=ctx.file.mimetype,
    )

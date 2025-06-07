from anystore.store.fs import DoesNotExist
from anystore.util import clean_dict
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ftm_datalake import __version__
from ftm_datalake.archive import archive
from ftm_datalake.logging import get_logger
from ftm_datalake.model import File
from ftm_datalake.settings import Settings

settings = Settings()
log = get_logger(__name__)
DEFAULT_ERROR = HTTPException(404)
BASE_HEADER = {"x-ftm-datalake-version": __version__}


def get_file_header(file: File) -> dict[str, str]:
    return clean_dict(
        {
            **BASE_HEADER,
            "x-ftm-datalake-dataset": file.dataset,
            "x-ftm-datalake-key": file.key,
            "x-ftm-datalake-sha1": file.content_hash,
            "x-ftm-datalake-name": file.name,
            "x-ftm-datalake-size": str(file.size),
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


def get_file_info(dataset: str, key: str) -> File:
    storage = archive.get_dataset(dataset)
    return storage.lookup_file(key)


def ensure_path_context(dataset: str, key: str) -> Context:
    with Errors():
        return Context(dataset=dataset, key=key, file=get_file_info(dataset, key))


def stream_file(ctx: Context) -> StreamingResponse:
    storage = archive.get_dataset(ctx.dataset)
    file = storage.lookup_file(ctx.key)
    return StreamingResponse(
        storage.stream_file(file),
        headers=ctx.headers,
        media_type=ctx.file.mimetype,
    )

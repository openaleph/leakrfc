from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from leakrfc import __version__
from leakrfc.api.auth import Token, create_access_token, ensure_auth_context
from leakrfc.api.util import Context, Errors, ensure_path_context, stream_file
from leakrfc.archive import get_archive
from leakrfc.logging import get_logger
from leakrfc.settings import ApiSettings, Settings

log = get_logger(__name__)

settings = Settings()
api_settings = ApiSettings()

app = FastAPI(
    debug=settings.debug,
    title=api_settings.title,
    # contact=api_settings.contact,
    description=api_settings.description,
    redoc_url="/",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(api_settings.allowed_origin)],
    allow_methods=["HEAD", "OPTIONS", "GET"],
)

archive = get_archive()
log.info(f"Archive: `{archive._storage.uri}`")


if settings.debug:
    log.warning("Api is running in debug mode!")

    @app.get("/{dataset}/{key:path}/token")
    async def get_token(
        response: Response,
        ctx: Context = Depends(ensure_path_context),
        exp: int | None = None,
    ) -> Token:
        """
        Obtain a temporary access token. This is for development purposes only!
        """
        with Errors():
            response.headers.update(ctx.headers)
            return Token(
                access_token=create_access_token(ctx.dataset, ctx.key, exp),
                token_type="Bearer",
            )


@app.head("/file")
async def head_file_by_token(
    response: Response, ctx: Context = Depends(ensure_auth_context)
) -> None:
    """
    Get metadata of a private file
    """
    with Errors():
        response.headers.update(ctx.headers)


@app.get("/file", response_model=None)
async def get_file_by_token(
    ctx: Context = Depends(ensure_auth_context),
) -> StreamingResponse:
    """
    Stream contents of a private file
    """
    with Errors():
        return stream_file(ctx)


@app.head("/{dataset}/{key:path}")
async def head_file(
    response: Response, ctx: Context = Depends(ensure_path_context)
) -> None:
    """
    Get metadata of a public file
    """
    with Errors():
        response.headers.update(ctx.headers)


@app.get("/{dataset}/{key:path}", response_model=None)
async def get_file(ctx: Context = Depends(ensure_path_context)) -> StreamingResponse:
    """
    Stream contents of a public file
    """
    with Errors():
        return stream_file(ctx)

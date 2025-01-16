from typing import Optional

from anystore.io import smart_read
from anystore.model import StoreModel
from pydantic import BaseModel, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from leakrfc.model import ArchiveModel


class Settings(BaseSettings):
    # model_config = SettingsConfigDict(cli_parse_args=True)

    debug: bool = False
    log_json: bool = False
    log_level: str = "INFO"

    aleph_secret_key: str = (
        "aleph-scrt"  # to act as a servicelayer replacement to the ui
    )


class ArchiveSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="leakrfc_",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        # cli_parse_args=True
    )

    uri: str | None = None
    archive: ArchiveModel | None = None
    cache: StoreModel | None = None
    cache_prefix: str = "leakrfc"


class ApiContactSettings(BaseModel):
    name: str | None
    url: str | None
    email: str | None


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="leakrfc_api_",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    secret_key: str = "change-for-production"
    access_token_expire: int = 5  # minutes
    access_token_algorithm: str = "HS256"

    title: str = "LeakRFC Api"
    description: str = smart_read("./README.md", mode="r")
    contact: ApiContactSettings | None = None

    allowed_origin: Optional[HttpUrl] = "http://localhost:3000"

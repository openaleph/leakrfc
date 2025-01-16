"""
https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

Authorization expects an encrypted bearer token with the dataset and key lookup
in the subject ({"sub": "<dataset>/<key>"}). Therefore, clients need to be able
to create such tokens (knowing the secret key) and handle dataset permissions.

Tokens should have a short expiration (via `exp` property in payload).
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from leakrfc.api.util import DEFAULT_ERROR, Context, ensure_path_context
from leakrfc.logging import get_logger
from leakrfc.settings import ApiSettings

settings = ApiSettings()
log = get_logger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/", auto_error=False)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    dataset: str
    key: str

    def __init__(self, **data):
        dataset, key = data.pop("sub").split("/", 1)
        data["dataset"] = dataset
        data["key"] = key
        super().__init__(**data)


def create_access_token(dataset: str, key: str, exp: int | None = None) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=exp or settings.access_token_expire)
    data = {"sub": f"{dataset}/{key}", "exp": expires}
    return jwt.encode(
        data, settings.secret_key, algorithm=settings.access_token_algorithm
    )


def ensure_token_context(token: str) -> Context:
    """Get context from url query argument"""

    if not token:
        log.error("Auth: no token")
        raise DEFAULT_ERROR
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.access_token_algorithm],
            verify=True,
        )
        data = TokenData(**payload)
        return ensure_path_context(data.dataset, data.key)
    except Exception as e:
        log.error(f"Invalid token: `{e}`", token=token)
        raise DEFAULT_ERROR


def ensure_auth_context(token: str = Depends(oauth2_scheme)) -> Context:
    """Get context from Authorization header"""

    return ensure_token_context(token)


# def ensure_aleph_context(token: str) -> Context:
#     """Decode legacy Aleph archive token"""

#     if not token:
#         raise DEFAULT_ERROR
#     try:
#         payload = jwt.decode(
#             token, settings.aleph_secret_key, algorithms=["HS256"], verify=True
#         )
#         key = payload["c"]
#         return ensure_path_context(data.dataset, key)
#     except Exception as e:
#         log.error(f"Invalid Aleph token: `{e}`", token=token)
#         raise DEFAULT_ERROR

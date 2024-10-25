import mimetypes
from typing import Any

from anystore.io import smart_open
from anystore.types import Uri
from anystore.util import make_checksum as _make_checksum
from jinja2 import Template
from pantomime import DEFAULT, normalize_mimetype


def make_checksum(uri: Uri, algorithm: str | None = "sha1") -> str:
    with smart_open(str(uri)) as io:
        return _make_checksum(io, algorithm)


def make_ch_key(ch: str) -> str:
    if len(ch) < 6:
        raise ValueError(f"Invalid checksum: `{ch}`")
    return "/".join((ch[:2], ch[2:4], ch[4:6], ch))


def guess_mimetype(value: Any) -> str | None:
    if not value:
        return
    guess = normalize_mimetype(value)
    if guess != DEFAULT:
        return guess
    mtype, _ = mimetypes.guess_type(value)
    return normalize_mimetype(mtype)


def render(tmpl: str, data: dict[str, Any]) -> str:
    template = Template(tmpl)
    return template.render(**data)

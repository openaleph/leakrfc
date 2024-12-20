import mimetypes
from typing import Any

from jinja2 import Template
from pantomime import DEFAULT, normalize_mimetype


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

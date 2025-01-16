import mimetypes
from typing import Any

from followthemoney import model
from jinja2 import Template
from rigour.mime import DEFAULT, normalize_mimetype, types


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


MIME_SCHEMAS = {
    (types.PDF, types.DOCX, types.WORD): model.get("Pages"),
    (types.HTML, types.XML): model.get("HyperText"),
    (types.CSV, types.EXCEL, types.XLS, types.XLSX): model.get("Table"),
    (types.PNG, types.GIF, types.JPEG, types.TIFF, types.DJVU, types.PSD): model.get(
        "Image"
    ),
    (types.OUTLOOK, types.OPF, types.RFC822): model.get("Email"),
    (types.PLAIN, types.RTF): model.get("PlainText"),
}


def mime_to_schema(mimetype: str) -> str:
    schema = model.get("Document")
    for mtypes, _schema in MIME_SCHEMAS.items():
        if mimetype in mtypes:
            schema = _schema
    if schema is not None:
        return schema.name
    return "Document"

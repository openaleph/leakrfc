"""
Extract source packages during archiving (crawl or make stage)
using [`patool`](https://pypi.org/project/patool/)
"""

from pathlib import Path
from typing import Any

import patoolib
from anystore.io import Uri
from anystore.store.virtual import get_virtual

from leakrfc.logging import get_logger
from leakrfc.model import OriginalFile

log = get_logger(__name__)


def extract_archive(source: Uri, temp_dir: Path, **kwargs: Any) -> None:
    patoolib.extract_archive(str(source), outdir=str(temp_dir), **kwargs)


def is_archive(file: OriginalFile) -> bool:
    return patoolib.is_archive(file.uri)


def handle_extract(file: OriginalFile, keep_source: bool | None = False) -> str | None:
    uri = file.uri[7:]
    try:
        with get_virtual("leakrfc-extract-", keep=True) as tmp:
            if keep_source:
                out = Path(tmp.path) / "/".join(map(str, Path(file.key).parents))
                out /= f"__extracted__/{file.name}"
            else:
                out = Path(tmp.path) / file.key
            out.mkdir(parents=True)
            extract_archive(uri, out, interactive=False)
            return tmp.path
    except Exception as e:
        log.error(f"Unable to extract `{uri}`: {e}")

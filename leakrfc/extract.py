"""
Extract source packages during archiving (crawl or make stage)
using [`patool`](https://pypi.org/project/patool/)
"""

from pathlib import Path
from typing import Any

import patoolib
from anystore.io import Uri
from anystore.store.virtual import get_virtual
from anystore.util import name_from_uri

from leakrfc.logging import get_logger
from leakrfc.model import OriginalFile

log = get_logger(__name__)


def extract_archive(source: Uri, temp_dir: Path, **kwargs: Any) -> None:
    patoolib.extract_archive(str(source), outdir=str(temp_dir), **kwargs)


def is_archive(file: OriginalFile) -> bool:
    return patoolib.is_archive(file.uri)


def handle_extract(file: OriginalFile) -> Path | None:
    uri = file.uri[7:]
    try:
        with get_virtual("leakrfc-extract-", keep=True) as tmp:
            out = Path(tmp.path) / "__extracted__" / name_from_uri(uri)
            out.mkdir(parents=True)
            extract_archive(uri, out, interactive=False)
            return out.parent.parent
    except Exception as e:
        log.error(f"Unable to extract `{uri}`: {e}")

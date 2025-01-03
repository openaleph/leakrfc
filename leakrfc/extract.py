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
from leakrfc.model import File

log = get_logger(__name__)


def extract_archive(source: Uri, temp_dir: Path, **kwargs: Any) -> None:
    patoolib.extract_archive(str(source), outdir=str(temp_dir), **kwargs)


def is_archive(file: File) -> bool:
    return patoolib.is_archive(file.uri)


def handle_extract(
    file: File,
    keep_source: bool | None = False,
    ensure_subdir: bool | None = False,
) -> str | None:
    if not file.is_local:
        raise ValueError(f"File `{file.uri}` is not a local accessible file.")
    uri = file.uri[7:]
    try:
        with get_virtual("leakrfc-extract-", keep=True) as tmp:
            path = Path(file.key).parent
            if keep_source:
                out = Path(tmp.path) / path
                if ensure_subdir:
                    out /= f"__extracted__/{file.name}"
            elif ensure_subdir:  # use package name as subdir for extracted members
                out = Path(tmp.path) / file.key
            else:
                out = Path(tmp.path) / path
            out.mkdir(parents=True, exist_ok=True)
            extract_archive(uri, out, interactive=False)
            return tmp.path
    except Exception as e:
        log.error(f"Unable to extract `{uri}`: {e}")

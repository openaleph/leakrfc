from datetime import datetime

from nomenklatura.dataset import DefaultDataset
from pantomime.types import PLAIN

from leakrfc.model import (
    ORIGIN_CONVERTED,
    ORIGIN_EXTRACTED,
    ORIGIN_ORIGINAL,
    ConvertedFile,
    ExtractedFile,
    OriginalFile,
)


def test_model():
    uri = "http://localhost:8000/src/utf.txt"
    file_id = "default-file-2928064cd9a743af30b720634dcffacdd84de23d"

    file = OriginalFile.from_uri(uri, content_hash="ch-root")
    assert file.origin == ORIGIN_ORIGINAL == "original"
    assert file.name == "utf.txt"
    assert file.mimetype == PLAIN
    assert file.dataset == DefaultDataset.name
    assert file.id == file_id
    data = file.model_dump()
    assert data["origin"] == ORIGIN_ORIGINAL

    proxy = file.to_proxy()
    assert proxy.id == file.id
    assert proxy.dataset.name == file.dataset
    assert proxy.first("fileName") == file.name

    # file processing stages

    extracted = ExtractedFile.from_uri(uri, archive=file.id, content_hash="ch-ex")
    assert extracted.origin == ORIGIN_EXTRACTED == "extracted"
    assert extracted.archive == file_id
    data = extracted.model_dump()
    assert data["origin"] == ORIGIN_EXTRACTED

    converted = ConvertedFile.from_uri(uri, root=file.id, content_hash="ch-cv")
    assert converted.origin == ORIGIN_CONVERTED == "converted"
    assert converted.root == file_id
    data = converted.model_dump()
    assert data["origin"] == ORIGIN_CONVERTED

    # documents

    doc = file.to_document()
    assert doc.key == file.key
    assert doc.content_hash == file.content_hash
    assert doc.size == file.size
    assert doc.mimetype == PLAIN
    assert doc.dataset == file.dataset
    assert doc.created_at < datetime.now()
    assert doc.updated_at < datetime.now()
    assert doc.created_at <= doc.updated_at
    assert doc.to_csv().startswith("utf.txt,ch-root,19,text/plain")

    doc = doc.from_csv(doc.to_csv(), "test_dataset")
    assert doc.key == file.key
    assert doc.content_hash == file.content_hash
    assert doc.size == file.size
    assert doc.to_csv().startswith("utf.txt,ch-root,19,text/plain")

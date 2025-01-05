from datetime import datetime

from ftmq.model import Dataset
from nomenklatura.dataset import DefaultDataset
from rigour.mime.types import PLAIN

from leakrfc.model import ORIGIN_ORIGINAL, DatasetModel, File


def test_model():
    uri = "http://localhost:8000/src/utf.txt"
    file_id = "default-file-2928064cd9a743af30b720634dcffacdd84de23d"

    file = File.from_uri(uri, content_hash="ch-root")
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


def test_model_dataset(fixtures_path):
    config = fixtures_path / "archive/test_dataset/.leakrfc/config.yml"
    dataset = DatasetModel.from_yaml_uri(config)
    assert isinstance(dataset, Dataset)
    assert Dataset(**dataset.model_dump())

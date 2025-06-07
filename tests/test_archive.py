from moto import mock_aws
from rigour.mime.types import PLAIN

from ftm_datalake.archive import get_archive, get_dataset
from ftm_datalake.archive.dataset import DatasetArchive, ReadOnlyDatasetArchive
from ftm_datalake.crawl import crawl
from ftm_datalake.model import ArchiveModel, DatasetModel
from tests.conftest import setup_s3


def _test_dataset(dataset: DatasetArchive | ReadOnlyDatasetArchive):
    files = [f for f in dataset.iter_files(use_db=False)]
    assert len(files) == 74
    files = [f for f in dataset.iter_files()]
    assert len(files) == 74

    keys = [f for f in dataset.iter_keys()]
    assert len(keys) == 74
    assert set(f.key for f in files) == set(keys)

    key = "utf.txt"
    content_hash = "5a6acf229ba576d9a40b09292595658bbb74ef56"

    # lookup by key
    assert dataset.exists(key)
    file = dataset.lookup_file(key)
    assert file.key == "utf.txt"
    assert file.content_hash == content_hash
    assert file.mimetype == PLAIN
    with dataset.open_file(file) as fh:
        assert fh.read() == "Îș unî©ođ€.\n".encode()

    assert b"\n".join(dataset.stream_file(file)) == "Îș unî©ođ€.\n".encode()

    return True


def test_archive_datasets():
    archive = get_archive()
    datasets = [a.name for a in archive.get_datasets()]
    assert set(datasets) == set(["test_dataset", "s3_dataset"])


def test_archive_dataset(test_dataset):
    assert test_dataset.config.ftm_datalake == ArchiveModel(**test_dataset.model_dump())
    test_dataset.make_index()

    # FIXME intervals key
    config1 = test_dataset.config.model_dump()
    config2 = test_dataset._storage.get(
        test_dataset._get_index_path(), model=DatasetModel
    ).model_dump()
    del config1["intervals"]
    del config2["intervals"]
    assert config1 == config2
    assert _test_dataset(test_dataset)


# def test_archive_remote_dataset():
#     dataset = _test_archive_dataset("remote_dataset")
#     assert dataset.store.readonly
#     assert dataset.readonly
#     assert isinstance(dataset, ReadOnlyDatasetArchive)


def test_archive_zip_dataset(fixtures_path):
    dataset = get_dataset(
        "test_dataset", uri=fixtures_path / "test_dataset.ftm_datalake"
    )
    assert _test_dataset(dataset)


# assert dataset.store.readonly
# assert dataset.readonly
# assert isinstance(dataset, ReadOnlyDatasetArchive)


# @mock_aws
# def test_archive_s3_dataset(fixtures_path):
#     setup_s3()
#     dataset = get_dataset("test_dataset", uri="s3://ftm_datalake", path_prefix=False)
#     crawl(fixtures_path / "src", dataset)
#     assert _test_dataset(dataset)

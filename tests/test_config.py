from anystore.store import MemoryStore

from leakrfc.archive import Archive, configure_archive, get_archive, get_dataset


def test_config(fixtures_path, monkeypatch, tmp_path):
    config = Archive._from_uri(fixtures_path / "archive.yml")
    archive = get_archive()
    assert config.storage.uri.strip(".") in archive._storage.uri
    assert archive._storage.uri.endswith("tests/fixtures/archive")
    assert archive._storage.serialization_mode == "raw"
    assert archive.checksum_algorithm == "sha1"
    assert archive.metadata_prefix == ".leakrfc"

    # overwrite some settings
    # monkeypatch.setenv("LEAKRFC_STORE__URI", "other-files")
    # monkeypatch.setenv("LEAKRFC_CACHE__URI", "redis://localhost")
    # archive = configure_archive()
    # assert archive.cache.scheme == "redis"
    # assert archive.store.uri.endswith("other-files")

    dataset = get_dataset("test_dataset")
    assert dataset.name == "test_dataset"
    assert dataset._storage.uri == f"{archive._storage.uri}/test_dataset"

    dataset = archive.get_dataset("test_dataset")
    assert dataset.name == "test_dataset"
    assert dataset._storage.uri == f"{archive._storage.uri}/test_dataset"

    dataset = get_dataset("test_dataset", uri="foo")
    assert dataset._storage.uri.endswith("foo")

    archive = get_archive(tmp_path / "foo.leakrfc")
    assert archive.is_zip
    dataset = archive.get_dataset("test")
    assert dataset._storage.uri == archive._storage.uri
    assert dataset._make_path() == "test"

    dataset = get_dataset("test_dataset", tmp_path / "foo2.leakrfc")
    assert dataset.is_zip
    assert dataset._make_path() == "test_dataset"

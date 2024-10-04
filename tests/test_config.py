from anystore.store import MemoryStore

from leakrfc.archive import Archive, configure_archive, get_archive, get_dataset


def test_config(fixtures_path, monkeypatch):
    config = Archive._from_uri(fixtures_path / "archive.yml")
    archive = get_archive()
    assert config.storage_config.uri.strip(".") in archive._storage.uri
    assert archive._storage.uri.endswith("tests/fixtures/archive")
    assert archive._storage.serialization_mode == "raw"
    assert archive.checksum_algorithm == "sha1"
    assert archive.metadata_prefix == ".leakrfc"
    assert isinstance(archive.cache, MemoryStore)

    # overwrite some settings
    # monkeypatch.setenv("LEAKRFC_STORE__URI", "other-files")
    # monkeypatch.setenv("LEAKRFC_CACHE__URI", "redis://localhost")
    # archive = configure_archive()
    # assert archive.cache.scheme == "redis"
    # assert archive.store.uri.endswith("other-files")

    dataset = get_dataset("test_dataset")
    assert dataset.name == "test_dataset"
    assert dataset._storage.uri.startswith(archive._storage.uri)
    assert isinstance(dataset.archive.cache, MemoryStore)

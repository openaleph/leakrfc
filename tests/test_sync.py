from anystore import get_store

from leakrfc.archive import get_dataset
from leakrfc.sync.memorious import import_memorious, iter_memorious


def test_sync_memorious(fixtures_path, tmp_path):
    memorious_uri = fixtures_path / "memorious"
    memorious = get_store(memorious_uri)
    file = next(iter_memorious(memorious, "memorious"))
    assert file.name == "Appleby_Gerry_sm.jpg"
    assert file.key == f"{file.path}/{file.name}"
    assert file.extra["title"] == "Home - BishopAccountability.org"
    assert file.mimetype == "image/jpeg"

    dataset = get_dataset("memorious", uri=tmp_path / "archive")
    dataset.archive_file(file.extra.pop("_file_name"), memorious, file)

    import_memorious(dataset, fixtures_path / "memorious/")
    archived_file = next(dataset.iter_files())
    assert archived_file.name == file.name
    assert archived_file.key == file.key

    assert dataset.exists_hash(file.content_hash)

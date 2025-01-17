from leakrfc.archive import get_dataset
from leakrfc.crawl import crawl
from leakrfc.make import make_dataset


def test_make(fixtures_path, tmp_path):
    dataset = get_dataset("test_dataset", uri=tmp_path / "test")
    crawl(fixtures_path / "src", dataset)
    res = make_dataset(dataset)
    assert res.files_total == 74
    assert res.integrity_errors == 0

    # delete a file info reference
    dataset._storage.delete(".leakrfc/meta/utf.txt/info.json")
    res = make_dataset(dataset)
    assert res.files_total == 74
    assert res.files_added == 1
    assert res.integrity_errors == 0

    # delete a source file
    dataset._storage.delete("utf.txt")
    res = make_dataset(dataset)
    assert res.files_total == 73
    assert res.files_deleted == 1
    assert res.integrity_errors == 0

    # checksum mismatch
    file = dataset.lookup_file("image.svg")
    original_ch = file.content_hash
    file.content_hash = "broken"
    dataset._put_file_info(file)
    res = make_dataset(dataset)
    assert res.files_total == 73
    assert res.integrity_errors == 1
    file = dataset.lookup_file("image.svg")
    assert file.content_hash == original_ch

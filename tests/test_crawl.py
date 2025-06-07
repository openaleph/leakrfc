from ftm_datalake.archive import get_dataset
from ftm_datalake.crawl import crawl


def test_crawl(tmp_path, fixtures_path):
    url = "http://localhost:8000/src"
    dataset = get_dataset("test", uri=tmp_path / "test1")
    crawl(url, dataset)
    files1 = [f for f in dataset.iter_files(use_db=False)]
    assert len(files1) == 74
    files1 = [f for f in dataset.iter_files()]
    assert len(files1) == 74

    dataset = get_dataset("test", uri=tmp_path / "test2")
    crawl(fixtures_path / "src", dataset)
    files2 = [f for f in dataset.iter_files()]
    assert len(files2) == 74

    files1 = {f.key for f in files1}
    files2 = {f.key for f in files2}
    assert not files1 - files2, files1 - files2
    assert not files2 - files1, files2 - files1

    file = dataset.lookup_file("testdir/test.txt")
    assert file.content_hash == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"
    assert file.key == "testdir/test.txt"
    assert file.name == "test.txt"


def test_crawl_globs(tmp_path, fixtures_path):
    dataset = get_dataset("test", uri=tmp_path / "test3")
    res = crawl(fixtures_path / "src", dataset, include="*.pdf")
    assert res.done == 12
    res = crawl(fixtures_path / "src", dataset, exclude="*.pdf")
    assert res.done == 74 - 12

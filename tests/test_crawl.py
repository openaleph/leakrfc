from leakrfc.archive import get_dataset
from leakrfc.crawl import crawl


def test_crawl(tmp_path, fixtures_path):
    url = "http://localhost:8000/src"
    dataset = get_dataset("crawled", uri=tmp_path / "test-archive")
    crawl(url, dataset, use_cache=False)
    files1 = [f for f in dataset.iter_files(use_db=False)]
    assert len(files1) == 74
    files1 = [f for f in dataset.iter_files()]
    assert len(files1) == 74

    dataset = get_dataset("crawled-local", uri=tmp_path / "test-archive")
    crawl(fixtures_path / "src", dataset, use_cache=False)
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


def test_crawl_extract(tmp_path, fixtures_path):
    dataset = get_dataset("crawled_extracted", uri=tmp_path / "test-archive")
    res = crawl(fixtures_path / "src", dataset, extract=True, use_cache=False)
    assert res.extracted == 28
    assert res.packages == 4
    assert res.extracted + res.done - res.packages == len(
        [f for f in dataset.iter_files()]
    )

    dataset = get_dataset("crawled_extracted-keep", uri=tmp_path / "test-archive")
    res = crawl(
        fixtures_path / "src",
        dataset,
        extract=True,
        extract_keep_source=True,
        use_cache=False,
    )
    assert res.extracted == 28
    assert res.packages == 4
    assert res.extracted + res.done == len([f for f in dataset.iter_files()])


def test_crawl_globs(tmp_path, fixtures_path):
    dataset = get_dataset("crawled-glob", uri=tmp_path / "test-archive")
    res = crawl(fixtures_path / "src", dataset, use_cache=False, include="*.pdf")
    assert res.done == 12
    res = crawl(fixtures_path / "src", dataset, use_cache=False, exclude="*.pdf")
    assert res.done == 74 - 12

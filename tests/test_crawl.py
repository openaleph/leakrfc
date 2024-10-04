from leakrfc.archive import get_dataset
from leakrfc.crawl import crawl


def test_crawl(tmp_path, fixtures_path):
    url = "http://localhost:8000/src"
    dataset = get_dataset("crawled", uri=tmp_path / "test-archive")
    crawl(url, dataset)
    files1 = [f for f in dataset.iter_files()]
    assert len(files1) == 74

    dataset = get_dataset("crawled-local", uri=tmp_path / "test-archive")
    crawl(fixtures_path / "src", dataset)
    files2 = [f for f in dataset.iter_files()]
    assert len(files2) == 74

    files1 = {f.key for f in files1}
    files2 = {f.key for f in files2}
    assert not files1 - files2, files1 - files2
    assert not files2 - files1, files2 - files1

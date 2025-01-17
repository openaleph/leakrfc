from leakrfc.archive import get_dataset
from leakrfc.crawl import crawl
from leakrfc.model import ORIGIN_EXTRACTED


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


def test_crawl_extract(tmp_path, fixtures_path):
    # default
    dataset = get_dataset("test0", uri=tmp_path / "test0")
    res = crawl(fixtures_path / "src", dataset, extract=True)
    assert res.extracted == 28
    assert res.packages == 4
    assert res.done == 74
    assert dataset.exists("tests/fixtures/500 pages.pdf")
    file = dataset.lookup_file("tests/fixtures/500 pages.pdf")
    assert file.origin == ORIGIN_EXTRACTED
    assert file.source_file == "500_pages.7z"
    assert dataset.exists("testdir/test-documents/testPDF.pdf")
    file = dataset.lookup_file("testdir/test-documents/testPDF.pdf")
    assert file.origin == ORIGIN_EXTRACTED
    assert file.source_file == "testdir/test-documents.rar"

    # ensure subdir
    dataset = get_dataset("test1", uri=tmp_path / "test1")
    res = crawl(
        fixtures_path / "src",
        dataset,
        extract=True,
        extract_ensure_subdir=True,
    )
    assert res.extracted == 28
    assert res.packages == 4
    assert res.extracted + res.done - res.packages == len(
        [f for f in dataset.iter_files()]
    )
    assert dataset.exists("500_pages.7z/tests/fixtures/500 pages.pdf")
    assert dataset.exists("testdir/test-documents.rar/test-documents/testPDF.pdf")

    url = "http://localhost:8000/src"
    dataset = get_dataset("test2", uri=tmp_path / "test2")
    res = crawl(url, dataset, extract=True, extract_ensure_subdir=True)
    assert res.extracted == 28
    assert res.packages == 4
    assert res.extracted + res.done - res.packages == len(
        [f for f in dataset.iter_files()]
    )
    assert dataset.exists("500_pages.7z/tests/fixtures/500 pages.pdf")
    assert dataset.exists("testdir/test-documents.rar/test-documents/testPDF.pdf")


def test_crawl_extract_keep(tmp_path, fixtures_path):
    dataset = get_dataset("test1", uri=tmp_path / "test1")
    res = crawl(
        fixtures_path / "src",
        dataset,
        extract=True,
        extract_keep_source=True,
        extract_ensure_subdir=True,
    )
    assert res.extracted == 28
    assert res.packages == 4
    assert res.extracted + res.done == len([f for f in dataset.iter_files()])
    assert dataset.exists("__extracted__/500_pages.7z/tests/fixtures/500 pages.pdf")
    assert dataset.exists(
        "testdir/__extracted__/test-documents.rar/test-documents/testPDF.pdf"
    )

    url = "http://localhost:8000/src"
    dataset = get_dataset("test2", uri=tmp_path / "test2")
    res = crawl(
        url,
        dataset,
        extract=True,
        extract_keep_source=True,
        extract_ensure_subdir=True,
    )
    assert res.extracted == 28
    assert res.packages == 4
    assert res.extracted + res.done == len([f for f in dataset.iter_files()])
    assert dataset.exists("__extracted__/500_pages.7z/tests/fixtures/500 pages.pdf")
    assert dataset.exists(
        "testdir/__extracted__/test-documents.rar/test-documents/testPDF.pdf"
    )


def test_crawl_globs(tmp_path, fixtures_path):
    dataset = get_dataset("test", uri=tmp_path / "test3")
    res = crawl(fixtures_path / "src", dataset, include="*.pdf")
    assert res.done == 12
    res = crawl(fixtures_path / "src", dataset, exclude="*.pdf")
    assert res.done == 74 - 12

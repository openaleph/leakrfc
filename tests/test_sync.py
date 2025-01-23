from anystore import get_store

from leakrfc.archive import get_dataset
from leakrfc.sync.memorious import (
    MemoriousWorker,
    get_file_key,
    get_file_name,
    get_file_name_strip_func,
    get_file_name_templ_func,
    import_memorious,
)


def test_sync_memorious(fixtures_path, tmp_path, monkeypatch):
    memorious_uri = fixtures_path / "memorious"
    memorious = get_store(memorious_uri)
    dataset = get_dataset("memorious", uri=tmp_path / "archive")
    worker = MemoriousWorker(memorious_uri, dataset=dataset)
    key = next(worker.get_tasks())
    file = worker.load_memorious(key)
    assert file.name == "Appleby_Gerry_sm.jpg"
    assert file.key == memorious._get_relpath(memorious.get_key(file.key))
    assert file.extra["title"] == "Home - BishopAccountability.org"
    assert file.mimetype == "image/jpeg"

    res = import_memorious(dataset, fixtures_path / "memorious/")
    assert res.added == 1
    assert res.skipped == 0
    archived_file = next(dataset.iter_files())
    assert archived_file.name == file.name
    assert archived_file.key == file.key

    # FIXME
    # monkeypatch.setenv("CACHE", "1")
    # # now cached
    # res = import_memorious(dataset, fixtures_path / "memorious/")
    # assert res.added == 0
    # assert res.skipped == 0  # cached
    # assert len([f for f in dataset.iter_files()]) == 1
    # archived_file = next(dataset.iter_files())
    # assert archived_file.name == file.name
    # assert archived_file.key == file.key

    # custom file key (path) method
    def get_key(data):
        return data["_file_name"]

    worker = MemoriousWorker(memorious_uri, get_key, dataset=dataset)
    key = next(worker.get_tasks())
    file = worker.load_memorious(key)
    assert file.name == file.key == file.extra["_file_name"]

    # key funcs
    data = {
        "url": "https://www.asktheeu.org/en/request/14928/response/55317/attach/5/Communication%20from%20the%20Commission%20SG%202009%20D%2051604.pdf?cookie_passthrough=1",
        "headers": {
            "Server": "nginx",
        },
    }
    assert (
        get_file_key(data)
        == "en/request/14928/response/55317/attach/5/Communication from the Commission SG 2009 D 51604.pdf"
    )
    assert (
        get_file_name(data) == "Communication from the Commission SG 2009 D 51604.pdf"
    )
    assert (
        get_file_name_strip_func("en/request")(data)
        == "14928/response/55317/attach/5/Communication from the Commission SG 2009 D 51604.pdf"
    )
    assert (
        get_file_name_strip_func("foo/bar")(data)
        == "en/request/14928/response/55317/attach/5/Communication from the Commission SG 2009 D 51604.pdf"
    )
    assert get_file_name_templ_func("{{ headers.Server }}.pdf")(data) == "nginx.pdf"

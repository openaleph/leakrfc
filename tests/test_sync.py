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


def test_sync_memorious(fixtures_path, tmp_path):
    memorious_uri = fixtures_path / "memorious"
    memorious = get_store(memorious_uri)
    dataset = get_dataset("memorious", uri=tmp_path / "archive")
    worker = MemoriousWorker(memorious_uri, dataset=dataset, use_cache=False)
    key = next(worker.get_tasks())
    file = worker.load_memorious(key)
    assert file.name == "Appleby_Gerry_sm.jpg"
    assert file.key == memorious._get_relpath(memorious.get_key(file.key))
    assert file.extra["title"] == "Home - BishopAccountability.org"
    assert file.mimetype == "image/jpeg"

    import_memorious(dataset, fixtures_path / "memorious/")
    archived_file = next(dataset.iter_files())
    assert archived_file.name == file.name
    assert archived_file.key == file.key

    assert dataset.exists_hash(file.content_hash)

    # now cached
    import_memorious(dataset, fixtures_path / "memorious/")

    # custom file key (path) method
    def get_key(data):
        return data["_file_name"]

    worker = MemoriousWorker(memorious_uri, get_key, dataset=dataset, use_cache=False)
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
    assert get_file_name_templ_func("{{ headers.Server }}.pdf")(data) == "nginx.pdf"

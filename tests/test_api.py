from fastapi.testclient import TestClient

from leakrfc.api import app
from leakrfc.archive import get_dataset
from leakrfc.crawl import crawl

client = TestClient(app)

DATASET = "test_dataset"
SHA1 = "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"
KEY = "testdir/test.txt"
URL = f"{DATASET}/{KEY}"


def _check_headers(res):
    assert "text/plain" in res.headers["content-type"]  # FIXME
    assert res.headers["x-leakrfc-dataset"] == DATASET
    assert res.headers["x-leakrfc-key"] == KEY
    assert res.headers["x-leakrfc-sha1"] == SHA1
    assert res.headers["x-leakrfc-name"] == "test.txt"
    assert res.headers["x-leakrfc-size"] == "11"
    return True


def test_api(fixtures_path, monkeypatch):
    dataset = get_dataset(DATASET)
    crawl(fixtures_path / "src", dataset)

    from leakrfc.api.util import settings

    monkeypatch.setattr(settings, "debug", False)
    # production mode always raises 404 on any errors

    res = client.get("/")
    assert res.status_code == 200

    res = client.head(URL)
    assert _check_headers(res)

    res = client.get(URL)
    assert _check_headers(res)

    # token access
    res = client.get("/file")
    assert res.status_code == 404

    res = client.get(URL + "/token?exp=1")
    token = res.json()["access_token"]
    header = {"Authorization": f"Bearer {token}"}
    res = client.head("/file", headers=header)
    assert res.status_code == 200
    assert _check_headers(res)

    # expired token
    res = client.get(URL + "/token?exp=-1")
    token = res.json()["access_token"]
    header = {"Authorization": f"Bearer {token}"}
    res = client.head("/file", headers=header)
    assert res.status_code == 404

    # invalid requests raise 404
    res = client.head("/foo/bar")
    assert res.status_code == 404

import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import aiobotocore.awsrequest
import aiobotocore.endpoint
import aiohttp
import aiohttp.client_reqrep
import aiohttp.typedefs
import boto3
import botocore.awsrequest
import botocore.model
import pytest
import requests

from leakrfc.archive import get_dataset
from leakrfc.archive.cache import get_cache
from leakrfc.archive.dataset import INFO_PREFIX, DatasetArchive
from leakrfc.crawl import crawl

# from anystore import get_store
# from anystore.mirror import mirror


FIXTURES_PATH = (Path(__file__).parent / "fixtures").absolute()


@pytest.fixture(scope="session")
def fixtures_path() -> Path:
    return FIXTURES_PATH


@pytest.fixture(scope="session")
def test_dataset(tmp_path_factory) -> DatasetArchive:
    tmp_path = tmp_path_factory.mktemp("test-archive")
    tmp_path.mkdir(parents=True, exist_ok=True)
    dataset = get_dataset("test_dataset", uri=tmp_path / "archive")
    crawl(FIXTURES_PATH / "src", dataset)
    return dataset


@pytest.hookimpl()
def pytest_sessionfinish():
    p = FIXTURES_PATH / "archive" / "test_dataset" / ".leakrfc"
    shutil.rmtree(p / INFO_PREFIX, ignore_errors=True)


@pytest.fixture(autouse=True)
def clear_memory_cache():
    get_cache.cache_clear()
    get_cache()._store = {}


# https://pawamoy.github.io/posts/local-http-server-fake-files-testing-purposes/
def spawn_and_wait_server():
    process = subprocess.Popen(
        [sys.executable, "-m", "RangeHTTPServer"], cwd=str(FIXTURES_PATH)
    )
    while True:
        try:
            requests.get("http://localhost:8000")
        except Exception:
            time.sleep(1)
        else:
            break
    return process


@pytest.fixture(scope="session", autouse=True)
def http_server():
    process = spawn_and_wait_server()
    yield process
    process.kill()
    process.wait()
    return


def setup_s3():
    s3 = boto3.resource("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="leakrfc")
    # from_store = get_store(uri=FIXTURES_PATH / "src", serialization_mode="raw")
    # to_store = get_store(uri="s3://leakrfc", serialization_mode="raw")
    # mirror(from_store, to_store)


# Mock s3 for fsspec
# https://github.com/aio-libs/aiobotocore/issues/755


class MockAWSResponse(aiobotocore.awsrequest.AioAWSResponse):
    """
    Mocked AWS Response.

    https://github.com/aio-libs/aiobotocore/issues/755
    https://gist.github.com/giles-betteromics/12e68b88e261402fbe31c2e918ea4168
    """

    def __init__(self, response: botocore.awsrequest.AWSResponse):
        self._moto_response = response
        self.status_code = response.status_code
        self.raw = MockHttpClientResponse(response)

    # adapt async methods to use moto's response
    async def _content_prop(self) -> bytes:
        return self._moto_response.content

    async def _text_prop(self) -> str:
        return self._moto_response.text


class MockHttpClientResponse(aiohttp.client_reqrep.ClientResponse):
    """
    Mocked HTP Response.

    See <MockAWSResponse> Notes
    """

    def __init__(self, response: botocore.awsrequest.AWSResponse):
        """
        Mocked Response Init.
        """

        async def read(self: MockHttpClientResponse, n: int = -1) -> bytes:
            return response.content

        self.content = MagicMock(aiohttp.StreamReader)
        self.content.read = read
        self.response = response

        self._loop = None

    @property
    def raw_headers(self) -> Any:
        """
        Return the headers encoded the way that aiobotocore expects them.
        """
        return {
            k.encode("utf-8"): str(v).encode("utf-8")
            for k, v in self.response.headers.items()
        }.items()


@pytest.fixture(scope="session", autouse=True)
def patch_aiobotocore() -> None:
    """
    Pytest Fixture Supporting S3FS Mocks.

    See <MockAWSResponse> Notes
    """

    def factory(original: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
        """
        Response Conversion Factory.
        """

        def patched_convert_to_response_dict(
            http_response: botocore.awsrequest.AWSResponse,
            operation_model: botocore.model.OperationModel,
        ) -> Any:
            return original(MockAWSResponse(http_response), operation_model)

        return patched_convert_to_response_dict

    aiobotocore.endpoint.convert_to_response_dict = factory(
        aiobotocore.endpoint.convert_to_response_dict
    )

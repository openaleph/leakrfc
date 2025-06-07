import pytest
from rigour.mime.types import DEFAULT, HTML, PDF, WORD

from ftm_datalake import util


def test_util():
    ch = "5a6acf229ba576d9a40b09292595658bbb74ef56"
    assert util.make_ch_key(ch) == f"5a/6a/cf/{ch}"
    assert util.make_ch_key("abcdef") == "ab/cd/ef/abcdef"
    with pytest.raises(ValueError):
        util.make_ch_key("abcde")

    assert util.guess_mimetype("foo.pdf") == "application/pdf"
    assert util.guess_mimetype("application/pdf") == "application/pdf"
    assert util.guess_mimetype("foo") == DEFAULT

    assert util.mime_to_schema(HTML) == "HyperText"
    assert util.mime_to_schema(PDF) == "Pages"
    assert util.mime_to_schema(WORD) == "Pages"
    assert util.mime_to_schema(DEFAULT) == "Document"
    assert util.mime_to_schema("foo") == "Document"

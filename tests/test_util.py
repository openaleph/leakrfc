import pytest
from pantomime import DEFAULT

from leakrfc import util


def test_util(fixtures_path):
    ch = "5a6acf229ba576d9a40b09292595658bbb74ef56"

    assert util.make_checksum(fixtures_path / "src" / "utf.txt") == ch

    assert util.make_ch_key(ch) == f"5a/6a/{ch}"
    assert util.make_ch_key("abcd") == "ab/cd/abcd"
    with pytest.raises(ValueError):
        util.make_ch_key("abc")

    assert util.guess_mimetype("foo.pdf") == "application/pdf"
    assert util.guess_mimetype("application/pdf") == "application/pdf"
    assert util.guess_mimetype("foo") == DEFAULT

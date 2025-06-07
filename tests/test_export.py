from ftm_datalake.archive import get_archive
from ftm_datalake.export import export_dataset


def test_export(tmp_path, test_dataset):
    out = tmp_path / "test_dataset.ftm_datalake"
    export_dataset(test_dataset, out)

    # verify
    keys = {f.content_hash for f in test_dataset.iter_files()}
    assert len(keys) == 74
    exported_dataset = get_archive(out).get_dataset("test_dataset")
    exported_keys = {f.content_hash for f in exported_dataset.iter_files()}
    assert not (keys - exported_keys)

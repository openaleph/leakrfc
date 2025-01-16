The aim of `leakrfc` is to provide a standardized and client agnostic way to share document collections and their metadata across systems. Collections must be syncable with standard tools (e.g. rsync, s3, ...) Therefore, no specific storage backend for metadata will be used. Every information needed is just stored in files.

Keeping the original file tree as is and storing all metadata in the subfolder `.leakrfc`, tenants of an archive don't even need to use the library to consume files.

The _RFC_ is reflected by the following layout structure for a _Dataset_:

```bash
./archive/
    my_dataset/  # the subfolder name is the `foreign_id` of a dataset

        # metadata maintained by `leakrfc`
        .leakrfc/
            index.json      # generated dataset metadata served for clients
            config.yml      # dataset configuration
            documents.csv   # document database (all metadata combined)
            size            # current sum of file size in bytes
            state/          # OPTIONAL processing state
                logs/
                created_at
                updated_at
            entities/       # OPTIONAL followthemoney entities for this dataset
                entities.ftm.json
            meta/                            # FILE METADATA STORAGE:
                .../File.doc/info.json       # - file metadata as json REQUIRED
                .../File.doc/txt             # - extracted plain text
                .../File.doc/converted.pdf   # - converted file, e.g. from .docx to .pdf for better web display
            export/         # OPTIONAL
                my_dataset.img.zst         # dump as image
                my_dataset.leakrfc         # dump as zipfile

        # actual source data
        File.doc
        Arbitrary Folder/
            Source1.pdf
            Tables/
                Another_File.xlsx
```

## Metadata

Documents metadata is stored in the `.leakrfc/documents.csv` file.

```csv
key,content_hash,size,mimetype,created_at,updated_at
106972554.pdf,54d6cd29c71713bd8b2b3c1267f13a4ab15e7c94,208679,application/pdf,2024-09-29 22:52:24.613038,2024-09-29 22:52:24.613038
500 pages.pdf,3e193f218e1dc0ae0f9f972da6d5da45b0abf59f,302661,application/pdf,2024-09-29 22:52:24.613038,2024-09-29 22:52:24.613038
```

This csv file is the aggregation of the json metadata stored for each file path in the `.leakrfc/meta/<path>` folder.

For example: `.leakrfc/meta/slides.ppt/info.json`

```json
{
  "created_at": "2024-09-29T22:52:24.673038",
  "updated_at": "2024-09-29T22:52:24.673038",
  "size": 148992,
  "name": "slides.ppt",
  "store": "/tests/fixtures/archive/test_dataset",
  "key": "slides.ppt",
  "dataset": "test_dataset",
  "content_hash": "08883b398cc03686df724621624f432d5d052bd4",
  "mimetype": "application/vnd.ms-powerpoint",
  "processed": null,
  "origin": "original",
  "source_file": null,
  "extra": {}
}
```

Arbitrary data can be stored in the `extra` key (or directly at the top level of the json object if it doesn't infer with the required metadata).

## Tracking updates

Each run of [crawl](./crawl.md), [make](./make.md) or other _adapters_ operations will update the documents metadata csv and produce a _diff_ from the current and last csv file with the changes. This follows the [unified diff format](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) so that clients can consume the changes and e.g. only process or import documents recently added.

Example of a `documents.csv.<timestamp>.diff` file:

```
---     2025-01-05T01:40:10.639414

+++     2025-01-15T13:32:49.955291

@@ -62,0 +63 @@

+test-documents.rar,9a377a36f36bff1c5de651b8f3162ae93c0fa4b1,67945,application/vnd.rar,2024-12-21 14:56:33.412859,2024-12-21 14:56:33.412859
```

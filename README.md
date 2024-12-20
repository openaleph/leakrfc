# leakrfc

_An RFC for leaks_

[leak-rfc.org](https://leak-rfc.org)

`leakrfc` provides a _data standard_ and _archive storage_ for leaked data, private and public document collections. The concepts and implementations are originally inspired by [mmmeta](https://github.com/simonwoerpel/mmmeta) and [Aleph's servicelayer archive](https://github.com/alephdata/servicelayer).

`leakrfc` acts as a standardized storage and retrieval mechanism for documents and their metadata. It provides an high-level interface for generating and sharing document collections and importing them into various analysis platforms, such as [_ICIJ Datashare_](https://datashare.icij.org/), [_Liquid Investigations_](https://github.com/liquidinvestigations/), and [_Aleph_](docs.aleph.occrp.org/).

It can act as a drop-in replacement for the underlying archive of [Aleph](https://docs.aleph.occrp.org/).

## install

```bash
pip install leakrfc
```

## build a dataset

`leakrfc` stores _metadata_ for the files that then refers to the actual _source file_.

List the files in a public accessible source (using [`anystore`](https://github.com/investigativedata/anystore/)):

```bash
ANYSTORE_URI="https://data.ddosecrets.com/Patriot%20Front/patriotfront/2021/Organizational%20Documents%20and%20Notes/" anystore keys
```

Crawl these documents into this _dataset_:

```bash
leakrfc -d ddos_patriotfront crawl "https://data.ddosecrets.com/Patriot%20Front/patriotfront/2021/Organizational%20Documents%20and%20Notes"
```

The _metadata_ and _source files_ are now stored in the archive (`./data` by default). All _metadata_ and other information lives in the `ddos_patriotfront/.leakrfc` subdirectory. Files are keyed and retrievable by their checksum (default: `sha1`).

Retrieve file metadata:

```bash
leakrfc -d ddos_patriotfront head "19338a97797bcc0eeb832cf7169cbbafc54ed255"
```

Retrieve actual file blob:

```bash
leakrfc -d ddos_patriotfront get "19338a97797bcc0eeb832cf7169cbbafc54ed255" > file.pdf
```

## api

### run api

```bash
export LEAKRFC_ARCHIVE__URI=./data
uvicorn leakrfc.api:app
```

### request a file

For public files:

```bash
# metadata only via headers
curl -I "http://localhost:5000/<dataset>/<sha1>"

# bytes stream of file
curl -s "http://localhost:5000/<dataset>/<sha1>" > /tmp/file.lrfc
```

Authorization expects an encrypted bearer token with the dataset and key lookup in the subject (token payload: `{"sub": "<dataset>/<key>"}`). Therefore, clients need to be able to create such tokens (knowing the secret key) and handle dataset permissions.

Tokens should have a short expiration (via `exp` property in payload).

```bash
# token in Authorization header
curl -H 'Authorization: Bearer <token>' ...

# metadata only via headers
curl -I "http://localhost:5000/file"

# bytes stream of file
curl -s "http://localhost:5000/file" > /tmp/file.s
```

## configure storage

```yaml
storage_config:
  uri: s3://my_bucket
  backend_kwargs:
    endpoint_url: https://s3.example.org
    aws_access_key_id: ${AWS_ACCESS_KEY_ID}
    aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
```

### pass through legacy aleph

```yaml
storage_config:
  uri: gcs://aleph_archive/
  legacy_aleph: true
  copy_over: true # subsequently merge legacy archive data into `leakrfc`
```

## layout

The _RFC_ is reflected by the following layout structure for a _Dataset_:

```bash
./archive/
    my_dataset/

        # metadata maintained by `leakrfc`
        .leakrfc/
            index.json      # generated dataset metadata served for clients
            config.yml      # dataset configuration
            documents.csv   # document database (all metadata combined)
            keys.csv        # hash -> uri mapping for all files
            state/          # processing state
                logs/
                created_at
                updated_at
            entities/
                entities.ftm.json
            files/                         # FILE METADATA STORAGE:
                a1/b1/a1b1c1.../info.json  # - file metadata as json REQUIRED
                a1/b1/a1b1c1.../txt        # - extracted plain text
                a1/b1/a1b1c1.../converted.pdf  # - converted file, e.g. from .docx to .pdf for better web display
                a1/b1/a1b1c1.../extracted/ # - extracted files from packages/archives
                    foo.txt
            export/
                my_dataset.img.zst         # dump as image
                my_dataset.leakrfc         # dump as zipfile

        # actual (read-only) data
        Arbitrary Folder/
            Source1.pdf
            Tables/
                Another_File.xlsx
```

### dataset config.yml

Follows the specification in [`ftmq.model.Dataset`](https://github.com/investigativedata/ftmq/blob/main/ftmq/model/dataset.py):

```yaml
name: my_dataset #  also known as "foreign_id"
title: An awesome leak
description: >
  Incidunt eum asperiores impedit. Nobis est dolorem et quam autem quo. Name
  labore sequi maxime qui non voluptatum ducimus voluptas. Exercitationem enim
  similique asperiores quod et quae maiores. Et accusantium accusantium error
  et alias aut omnis eos. Omnis porro sit eum et.
updated_at: 2024-09-25
index_url: https://static.example.org/my_dataset/index.json
# add more metadata

leakrfc: # see above
```

## Development

This package is using [poetry](https://python-poetry.org/) for packaging and dependencies management, so first [install it](https://python-poetry.org/docs/#installation).

Clone this repository to a local destination.

Within the repo directory, run

    poetry install --with dev

This installs a few development dependencies, including [pre-commit](https://pre-commit.com/) which needs to be registered:

    poetry run pre-commit install

Before creating a commit, this checks for correct code formatting (isort, black) and some other useful stuff (see: `.pre-commit-config.yaml`)

### testing

`leakrfc` uses [pytest](https://docs.pytest.org/en/stable/) as the testing framework.

    make test

## License and Copyright

`leakrfc`, (C) 2024 investigativedata.io

`leakrfc` is licensed under the AGPLv3 or later license.

see [NOTICE](./NOTICE) and [LICENSE](./LICENSE)

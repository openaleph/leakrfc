# leakrfc

"_A RFC for leaks_"

[leak-rfc.org](https://leak-rfc.org)

`leakrfc` provides a _data standard_ and _archive storage_ for leaked data, private and public document collections. The concepts and implementations are originally inspired by [mmmeta](https://github.com/simonwoerpel/mmmeta) and [Aleph's servicelayer archive](https://github.com/alephdata/servicelayer).

`leakrfc` acts as a multi-tenant storage and retrieval mechanism for documents and their metadata. It provides a high-level interface for generating and sharing document collections and importing them into various search and analysis platforms, such as [_ICIJ Datashare_](https://datashare.icij.org/), [_Liquid Investigations_](https://github.com/liquidinvestigations/), and [_Aleph_](https://docs.aleph.occrp.org/).

## Installation

Requires python 3.11 or later.

```bash
pip install leakrfc
```

## Documentation

[docs.investigraph.dev/lib/leakrfc](https://docs.investigraph.dev/lib/leakrfc)

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
`leakrfc`, (C) 2025 investigativedata.io

`leakrfc` is licensed under the AGPLv3 or later license.

see [NOTICE](./NOTICE) and [LICENSE](./LICENSE)

from typing import Annotated, Any, Optional, TypedDict

import orjson
import typer
from anystore.io import DEFAULT_WRITE_MODE, smart_open, smart_write
from anystore.util import clean_dict
from pydantic import BaseModel
from rich.console import Console

from leakrfc import __version__
from leakrfc.archive import configure_archive, get_dataset
from leakrfc.archive.dataset import DatasetArchive
from leakrfc.crawl import crawl
from leakrfc.exceptions import ImproperlyConfigured
from leakrfc.export import export_dataset
from leakrfc.logging import configure_logging
from leakrfc.make import make_dataset
from leakrfc.model import DatasetModel
from leakrfc.settings import ArchiveSettings, Settings
from leakrfc.sync.aleph import sync_to_aleph
from leakrfc.sync.aleph_entities import load_catalog, load_dataset
from leakrfc.sync.memorious import (
    get_file_name,
    get_file_name_strip_func,
    get_file_name_templ_func,
    import_memorious,
)

settings = Settings()
archive_settings = ArchiveSettings()
cli = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=settings.debug)
memorious = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=settings.debug)
aleph = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=settings.debug)
cli.add_typer(memorious, name="memorious", help="Memorious related operations")
cli.add_typer(aleph, name="aleph", help="Aleph related operations")
console = Console(stderr=True)


class State(TypedDict):
    dataset: DatasetArchive | None


STATE: State = {"dataset": None}


def write_obj(obj: BaseModel | None, out: str) -> None:
    if out == "-":
        console.print(obj)
    else:
        if obj is not None:
            smart_write(
                out, orjson.dumps(obj.model_dump(), option=orjson.OPT_APPEND_NEWLINE)
            )


class ErrorHandler:
    def __enter__(self) -> Any:
        pass

    def __exit__(self, exc_cls, exc, _):
        if exc_cls is not None:
            if isinstance(exc, BrokenPipeError):
                return
            if settings.debug:
                raise exc
            console.print(f"[red][bold]{exc_cls.__name__}[/bold]: {exc}[/red]")
            raise typer.Exit(code=1)


class Dataset(ErrorHandler):
    def __enter__(self) -> DatasetArchive:
        if not STATE["dataset"]:
            e = ImproperlyConfigured("Specify dataset foreign_id with `-d` option!")
            if settings.debug:
                raise e
            console.print(f"[red][bold]{e.__class__.__name__}[/bold]: {e}[/red]")
            raise typer.Exit(code=1)
        return STATE["dataset"]


@cli.callback(invoke_without_command=True)
def cli_leakrfc(
    version: Annotated[Optional[bool], typer.Option(..., help="Show version")] = False,
    dataset: Annotated[
        str | None, typer.Option("-d", help="Dataset foreign_id")
    ] = None,
):
    if version:
        console.print(__version__)
        raise typer.Exit()
    configure_logging(level=settings.log_level)
    if dataset:
        STATE["dataset"] = get_dataset(dataset)


@cli.command("config")
def cli_config():
    """
    Print current runtime configuration for base archive or given dataset
    """
    with ErrorHandler():
        archive = configure_archive()
        dataset = STATE["dataset"]
        write_obj(settings, "-")
        write_obj(archive, "-")
        write_obj(archive_settings.cache, "-")
        write_obj(dataset, "-")


@cli.command("catalog")
def cli_catalog(
    out_uri: Annotated[str, typer.Option("-o")] = "-",
    collect_stats: Annotated[
        bool, typer.Option(help="Collect document statistics")
    ] = False,
    names_only: Annotated[
        bool, typer.Option(help="Only show dataset names (`foreign_id`)")
    ] = False,
):
    """
    Show catalog for all existing datasets
    """
    with ErrorHandler():
        archive = configure_archive()
        if names_only:
            datasets = set()
            for dataset in archive.get_datasets():
                datasets.add(dataset.name)
            data = "\n".join(sorted(datasets))
            smart_write(out_uri, data.encode() + b"\n")
        else:
            catalog = archive.make_catalog(collect_stats=collect_stats)
            data = clean_dict(catalog.model_dump(mode="json"))
            smart_write(out_uri, orjson.dumps(data, option=orjson.OPT_APPEND_NEWLINE))


@cli.command("versions")
def cli_versions():
    """Show versions of dataset"""
    with Dataset() as dataset:
        for version in dataset.documents.get_versions():
            console.print(version)


@cli.command("diff")
def cli_diff(
    version: Annotated[str, typer.Option("-v", help="Version")],
    out_uri: Annotated[str, typer.Option("-o")] = "-",
):
    """
    Show documents diff for given version
    """
    with Dataset() as dataset:
        ver = dataset.documents.get_version(version)
        with smart_open(out_uri, DEFAULT_WRITE_MODE) as out:
            out.write(ver)


@cli.command("make")
def cli_make(
    out_uri: Annotated[str, typer.Option("-o")] = "-",
    use_cache: Annotated[Optional[bool], typer.Option(help="Use runtime cache")] = True,
    check_integrity: Annotated[
        Optional[bool], typer.Option(help="Check checksums")
    ] = True,
    cleanup: Annotated[
        Optional[bool], typer.Option(help="Cleanup (delete) unreferenced metadata")
    ] = True,
    metadata_only: Annotated[
        Optional[bool], typer.Option(help="Check document metadata only")
    ] = False,
    dataset_metadata_only: Annotated[
        Optional[bool], typer.Option(help="Compute dataset metadata only")
    ] = False,
):
    """
    Make or update a leakrfc dataset and check integrity
    """
    with Dataset() as dataset:
        if dataset_metadata_only:
            dataset.make_index()
            obj = dataset._storage.get(dataset._get_index_path(), model=DatasetModel)
        else:
            obj = make_dataset(
                dataset, use_cache, check_integrity, cleanup, metadata_only
            )
        write_obj(obj, out_uri)


@cli.command("get")
def cli_get(key: str, out_uri: Annotated[str, typer.Option("-o")] = "-"):
    """
    Retrieve a file from dataset archive and write to out uri (default: stdout)
    """
    with Dataset() as dataset:
        file = dataset.lookup_file(key)
        with dataset.open_file(file) as i, smart_open(out_uri, "wb") as o:
            o.write(i.read())


@cli.command("head")
def cli_head(key: str, out_uri: Annotated[str, typer.Option("-o")] = "-"):
    """
    Retrieve a file info from dataset archive and write to out uri (default: stdout)
    """
    with Dataset() as dataset:
        smart_write(
            out_uri,
            orjson.dumps(
                dataset.lookup_file(key).model_dump(),
                option=orjson.OPT_APPEND_NEWLINE,
            ),
        )


@cli.command("ls")
def cli_ls(
    out_uri: Annotated[str, typer.Option("-o")] = "-",
    keys: Annotated[bool, typer.Option(help="Show only keys")] = False,
    checksums: Annotated[bool, typer.Option(help="Show only checksums")] = False,
):
    """
    List all files in dataset archive
    """
    with Dataset() as dataset:
        if keys:
            files = (f.key.encode() + b"\n" for f in dataset.iter_files())
        elif checksums:
            files = (f.content_hash.encode() + b"\n" for f in dataset.iter_files())
        else:
            files = (
                orjson.dumps(f.model_dump(), option=orjson.OPT_APPEND_NEWLINE)
                for f in dataset.iter_files()
            )
        with smart_open(out_uri, "wb") as o:
            o.writelines(files)


@cli.command("crawl")
def cli_crawl(
    uri: str,
    out_uri: Annotated[
        str, typer.Option("-o", help="Write results to this destination")
    ] = "-",
    use_cache: Annotated[Optional[bool], typer.Option(help="Use runtime cache")] = True,
    skip_existing: Annotated[
        Optional[bool],
        typer.Option(
            help="Skip already existing files (doesn't check actual similarity)"
        ),
    ] = True,
    extract: Annotated[
        Optional[bool], typer.Option(help="Extract archives via `patool`")
    ] = False,
    extract_keep_source: Annotated[
        Optional[bool], typer.Option(help="Keep the source archive when extracting")
    ] = False,
    extract_ensure_subdir: Annotated[
        Optional[bool],
        typer.Option(
            help="Ensure a subdirectory with the package filename when extracting"
        ),
    ] = False,
    exclude: Annotated[
        Optional[str], typer.Option(help="Exclude paths glob pattern")
    ] = None,
    include: Annotated[
        Optional[str], typer.Option(help="Include paths glob pattern")
    ] = None,
):
    """
    Crawl documents from local or remote sources
    """
    with Dataset() as dataset:
        write_obj(
            crawl(
                uri,
                dataset,
                use_cache=use_cache,
                skip_existing=skip_existing,
                extract=extract,
                extract_keep_source=extract_keep_source,
                extract_ensure_subdir=extract_ensure_subdir,
                exclude=exclude,
                include=include,
            ),
            out_uri,
        )


@cli.command("export")
def cli_export(out: str):
    """
    Export a complete dataset in LeakRFC format
    """
    with Dataset() as dataset:
        write_obj(export_dataset(dataset, out), "-")


@memorious.command("sync")
def cli_sync_memorious(
    uri: Annotated[str, typer.Option("-i")],
    use_cache: Annotated[Optional[bool], typer.Option(help="Use runtime cache")] = True,
    name_only: Annotated[
        Optional[bool], typer.Option(help="Use only file name as key")
    ] = False,
    strip_prefix: Annotated[
        Optional[str], typer.Option(help="Strip from file key prefix")
    ] = None,
    key_template: Annotated[
        Optional[str], typer.Option(help="Template to generate key")
    ] = None,
):
    """
    Sync a memorious data store into a leakrfc dataset
    """
    with Dataset() as dataset:
        if name_only:
            key_func = get_file_name
        elif strip_prefix:
            key_func = get_file_name_strip_func(strip_prefix)
        elif key_template:
            key_func = get_file_name_templ_func(key_template)
        else:
            key_func = None
        res = import_memorious(dataset, uri, key_func, use_cache=use_cache)
        write_obj(res, "-")


@aleph.command("sync")
def cli_aleph_sync(
    use_cache: Annotated[Optional[bool], typer.Option(help="Use runtime cache")] = True,
    host: Annotated[Optional[str], typer.Option(help="Aleph host")] = None,
    api_key: Annotated[Optional[str], typer.Option(help="Aleph api key")] = None,
    folder: Annotated[Optional[str], typer.Option(help="Base folder path")] = None,
    foreign_id: Annotated[
        Optional[str], typer.Option(help="Aleph foreign_id (if different from dataset)")
    ] = None,
    metadata: Annotated[
        Optional[bool], typer.Option(help="Update collection metadata")
    ] = True,
):
    """
    Sync a leakrfc dataset to Aleph
    """
    with Dataset() as dataset:
        res = sync_to_aleph(
            dataset=dataset,
            host=host,
            api_key=api_key,
            prefix=folder,
            foreign_id=foreign_id,
            use_cache=use_cache,
            metadata=metadata,
        )
        write_obj(res, "-")


@aleph.command("load-dataset")
def cli_aleph_load_dataset(
    uri: Annotated[str, typer.Argument(help="Dataset index.json uri")],
    use_cache: Annotated[Optional[bool], typer.Option(help="Use runtime cache")] = True,
    host: Annotated[Optional[str], typer.Option(help="Aleph host")] = None,
    api_key: Annotated[Optional[str], typer.Option(help="Aleph api key")] = None,
    foreign_id: Annotated[
        Optional[str], typer.Option(help="Aleph foreign_id (if different from dataset)")
    ] = None,
    metadata: Annotated[
        Optional[bool], typer.Option(help="Update collection metadata")
    ] = True,
):
    """
    Load entities into an Aleph instance
    """
    with ErrorHandler():
        res = load_dataset(
            uri,
            host=host,
            api_key=api_key,
            foreign_id=foreign_id,
            use_cache=use_cache,
            metadata=metadata,
        )
        write_obj(res, "-")


@aleph.command("load-catalog")
def cli_aleph_load_catalog(
    uri: Annotated[str, typer.Argument(help="Catalog index.json uri")],
    # include_dataset: Annotated[
    #     Optional[list[str]],
    #     typer.Argument(help="Dataset foreign_ids to include, can be a glob"),
    # ] = None,
    # exclude_dataset: Annotated[
    #     Optional[list[str]],
    #     typer.Argument(help="Dataset foreign_ids to exclude, can be a glob"),
    # ] = None,
    use_cache: Annotated[Optional[bool], typer.Option(help="Use runtime cache")] = True,
    host: Annotated[Optional[str], typer.Option(help="Aleph host")] = None,
    api_key: Annotated[Optional[str], typer.Option(help="Aleph api key")] = None,
    metadata: Annotated[
        Optional[bool], typer.Option(help="Update collection metadata")
    ] = True,
):
    """
    Load entities into an Aleph instance
    """
    with ErrorHandler():
        for res in load_catalog(
            uri,
            host=host,
            api_key=api_key,
            # include_dataset=include_dataset,
            # exclude_dataset=exclude_dataset,
            use_cache=use_cache,
            metadata=metadata,
        ):
            write_obj(res, "-")

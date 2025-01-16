"""
Documents metadata database

CSV format:
key,content_hash,size,mimetype,created_at,updated_at
"""

import csv
from datetime import datetime
from difflib import unified_diff
from io import StringIO
from typing import TYPE_CHECKING, ContextManager, Literal, TextIO

import pandas as pd
from anystore.io import DoesNotExist, logged_items
from anystore.types import StrGenerator
from ftmq.types import CEGenerator

from leakrfc.archive.cache import get_cache
from leakrfc.logging import get_logger
from leakrfc.model import Docs, Document
from leakrfc.settings import ArchiveSettings

if TYPE_CHECKING:
    from leakrfc.archive import DatasetArchive

log = get_logger(__name__)
settings = ArchiveSettings()


class Documents:
    HEADER = ("key", "content_hash", "size", "mimetype", "created_at", "updated_at")

    def __init__(self, dataset: "DatasetArchive") -> None:
        self.cache = get_cache()
        self.dataset = dataset
        self.prefix = f"{settings.cache_prefix}/{dataset.name}/documents"
        self.ix_prefix = f"{dataset.name}/reversed"
        self.csv_path = dataset._get_documents_path()
        self._build_reversed = False

    def __iter__(self) -> Docs:
        yield from self.iter_documents()

    def get_db(self) -> pd.DataFrame:
        try:
            with self.open() as fh:
                return pd.read_csv(fh)
        except DoesNotExist:
            return pd.DataFrame(columns=self.HEADER)

    def make_db(self, documents: Docs) -> pd.DataFrame:
        df = pd.DataFrame(d.model_dump(exclude={"dataset"}) for d in documents)
        if len(df):
            return df
        return pd.DataFrame(columns=self.HEADER)

    def iter_documents(self) -> Docs:
        df = self.get_db()
        for _, row in logged_items(
            df.iterrows(),
            uri=self.dataset._get_documents_path(),
            action="Load",
            item_name="Document",
        ):
            data = dict(row)
            data["dataset"] = self.dataset.name
            yield Document(**data)

    def iter_entities(self) -> CEGenerator:
        for document in self.iter_documents():
            yield document.to_proxy()

    def add(self, doc: Document) -> None:
        """Mark a document for addition /change"""
        self.cache.put(f"{self.prefix}/add/{doc.key}", doc)

    def delete(self, doc: Document) -> None:
        """Mark a document for deletion"""
        self.cache.put(f"{self.prefix}/del/{doc.key}", doc)

    def write(self) -> None:
        """Write out documents database to csv with diff file"""
        log.info("Calculating diff ...", uri=self.csv_path)
        now = datetime.now().isoformat()
        current = self.get_db()
        added = self.make_db(self.pop_cache("add"))
        deleted = self.make_db(self.pop_cache("del"))
        new = pd.concat((current, added))
        new = new[~new["key"].isin(deleted["key"])]
        new = new.sort_values(["key", "updated_at"]).drop_duplicates(
            subset=["key"], keep="last"
        )
        log.info("Writing documents database ...", uri=self.csv_path)

        current_lines = self.make_lines(current)
        new_lines = self.make_lines(new)
        diff = list(
            unified_diff(
                current_lines,
                new_lines,
                fromfiledate=self.get_current_version(),
                tofiledate=now,
                n=0,
            )
        )
        if len(diff):
            # documents.csv.{timestamp}
            with self.open("w", now) as f:
                new.to_csv(f, index=False)
            # documents.csv.{timestamp}.diff
            with self.open("w", f"{now}.diff") as f:
                for line in diff:
                    f.write(line + "\n")
        # documents.csv
        with self.open("w") as f:
            new.to_csv(f, index=False)

    def pop_cache(self, prefix: Literal["add", "del"]) -> Docs:
        for key in self.cache.iterate_keys(prefix=f"{self.prefix}/{prefix}"):
            data = self.cache.pop(key)
            data["dataset"] = self.dataset.name
            yield Document(**data)

    def get_total_size(self) -> int:
        df = self.get_db()
        return int(df["size"].sum())

    def make_lines(self, df: pd.DataFrame) -> list[str]:
        lines: set[str] = set()
        for _, row in df.iterrows():
            io = StringIO()
            writer = csv.DictWriter(io, self.HEADER)
            writer.writerow(dict(row))
            lines.add(io.getvalue().strip())
        return list(sorted(lines))

    def open(
        self, mode: Literal["r", "w"] | None = "r", suffix: str | None = None
    ) -> ContextManager[TextIO]:
        key = self.dataset._get_documents_path(suffix=suffix)
        return self.dataset._storage.open(key, mode=mode)

    def get_versions(self) -> list[str]:
        keys: list[str] = []
        glob = self.dataset._make_path(
            self.dataset.metadata_prefix, "documents.csv.*.diff"
        )
        for key in self.dataset._storage.iterate_keys(glob=glob):
            ts = key[:-5].split("documents.csv.")[-1]
            keys.append(ts)
        return list(sorted(keys))

    def get_current_version(self) -> str:
        revs = self.get_versions()
        if revs:
            return revs[-1]
        return ""

    def get_version(self, version: str) -> str:
        key = f"documents.csv.{version}.diff"
        path = self.dataset._make_path(self.dataset.metadata_prefix, key)
        return self.dataset._storage.get(path)

    def get_keys_added(self, version: str) -> StrGenerator:
        key = f"documents.csv.{version}.diff"
        path = self.dataset._make_path(self.dataset.metadata_prefix, key)
        for line in self.dataset._storage.stream(path, mode="r"):
            if line.startswith("+") and not line.startswith("+++"):
                io = StringIO(line[1:])
                reader = csv.reader(io)
                for row in reader:
                    yield row[0]
                    break

    def get_keys_deleted(self, version: str) -> StrGenerator:
        key = f"documents.csv.{version}.diff"
        path = self.dataset._make_path(self.dataset.metadata_prefix, key)
        for line in self.dataset._storage.stream(path, mode="r"):
            if line.startswith("-") and not line.startswith("---"):
                io = StringIO(line)
                reader = csv.reader(io)
                for row in reader:
                    yield row[0]
                    break

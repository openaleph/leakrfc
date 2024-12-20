"""
Documents metadata database

CSV format:
key,content_hash,size,mimetype,created_at,updated_at
"""

import typing
from functools import cached_property

import pandas as pd

from leakrfc.archive.cache import get_cache
from leakrfc.logging import get_logger
from leakrfc.model import Docs, Document

if typing.TYPE_CHECKING:
    from leakrfc.archive import DatasetArchive

log = get_logger(__name__)


class Documents:
    HEADER = ("key", "content_hash", "size", "mimetype", "created_at", "updated_at")

    def __init__(self, dataset: "DatasetArchive") -> None:
        self.cache = get_cache()
        self.dataset = dataset
        self.prefix = f"{dataset.name}/documents"
        self.ix_prefix = f"{dataset.name}/reversed"
        self.csv_path = dataset._get_documents_path()
        self._build_reversed = False

    def __iter__(self) -> Docs:
        for ix, row in enumerate(self.dataset._storage.stream(self.csv_path, mode="r")):
            if ix:
                yield Document.from_csv(row, self.dataset.name)

    @cached_property
    def db(self) -> pd.DataFrame:
        try:
            with self.dataset._storage.open(self.csv_path) as io:
                return pd.read_csv(io)
        except Exception:
            return pd.DataFrame(columns=self.HEADER)

    def build_reversed(self) -> None:
        # build reversed hash -> key index
        if self._build_reversed:
            return
        log.info(
            "Building reversed index ...",
            dataset=self.dataset.name,
            cache=self.cache.uri,
        )
        for doc in self:
            self.cache.put(f"{self.ix_prefix}/{doc.content_hash}", doc.key)

    def put(self, doc: Document) -> None:
        self.cache.put(f"{self.prefix}/{doc.key}", doc.to_csv())

    def write(self) -> int:
        log.info("Writing documents ...", uri=self.csv_path)
        df = self.get_merged()
        with self.dataset._storage.open(self.csv_path, "wb") as o:
            df.to_csv(o, index=False)
        return len(df)

    def get_merged(self) -> pd.DataFrame:
        cache = pd.DataFrame(
            d.model_dump(exclude={"dataset"}) for d in self.iter_cache()
        )
        df = pd.concat((self.db, cache))
        return df.drop_duplicates(subset=("key", "content_hash")).sort_values("key")

    def iter_cache(self) -> Docs:
        for key in self.cache.iterate_keys(prefix=self.prefix):
            value = self.cache.get(key, serialization_mode="raw")
            yield Document.from_csv(value.decode(), self.dataset.name)

    def iter_db(self) -> Docs:
        for row in self.db.itertuples():
            yield Document(dataset=self.dataset.name, **dict(row))

    def iter_merged(self) -> Docs:
        for _, row in self.get_merged():
            yield Document(dataset=self.dataset.name, **dict(row))

    def get_key_for_content_hash(self, ch: str) -> str:
        self.build_reversed()
        return self.cache.get(f"{self.ix_prefix}/{ch}")

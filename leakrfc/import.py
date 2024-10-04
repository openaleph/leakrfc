# from anystore.io import smart_open
# from anystore.mixins import orjson
# from anystore.store import ZipStore
# from anystore.types import Uri

# from leakrfc.archive import Archive
# from leakrfc.logging import get_logger
# from leakrfc.model import File
# from leakrfc.util import make_ch_key

# log = get_logger(__name__)


# def import_dataset(uri: Uri, archive: Archive) -> None:
#     log.info(f"Importing dataset `{uri}`...", archive=archive.file_store.uri)
#     in_file = ZipStore(uri=uri, prefix=dataset.name)
#     proxies = b""
#     for info in dataset.iter_files():
#         proxies += orjson.dumps(
#             info.to_proxy().to_dict(), option=orjson.OPT_APPEND_NEWLINE
#         )
#         meta_key = f".leakrfc/meta/{make_ch_key(info.content_hash)}"
#         out.put(meta_key, info, model=File)
#         log.info(
#             f"Adding file `{info.name} ({info.content_hash})` metadata ...",
#             dataset=dataset.name,
#             store=dataset.file_store.uri,
#         )
#         with out.open(info.key, mode="wb") as o:
#             o.write(i.read())
#     out.put(".leakrfc/entities/entities.ftm.json", proxies)

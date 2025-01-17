Import [memorious](https://github.com/alephdata/memorious) crawler results into a `leakrfc` dataset.

As long as using the global cache (environment `CACHE=1`, default) only new documents are synced.

```bash
leakrfc -d my_dataset memorious sync -i /memorious/data/store/my_dataset
```

File paths can be set via a `key_func` function or via command line:

```bash
# use only the file names without their path:
leakrfc -d my_dataset memorious sync -i /memorious/data/store/my_dataset --name-only

# strip a prefix from the original relative file urls:
leakrfc -d my_dataset memorious sync -i /memorious/data/store/my_dataset --strip-prefix "assets/docs"
```

Or use a template that will replace values from the original memorious "\*.json" file for the source file. Given a json file stored by memorious like this:

```json
{
  "url": "https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-11840.pdf",
  "page": 5228,
  "request_id": "GET:https#//pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-11840.pdf",
  "status_code": 200,
  "content_hash": "123fd201b54d7a6c91e6e9852008c3ad6698ffbe",
  "headers": {},
  "retrieved_at": "2025-01-09T08:53:58.545052",
  "originator": "Senatsverwaltung für Inneres, Digitalisierung und Sport",
  "subject": "Öffentliche Verwaltung",
  "state": "Berlin",
  "category": "Beratungsvorgang",
  "doc_type": "Anfrage",
  "date": "2022-05-24",
  "doc_id": "BLN_V359641_D359643",
  "reference": "Drucksache 19/11840",
  "reference_id": "9/11840",
  "legislative_term": "9",
  "title": "Berlin - Antwort. Senatsverwaltung für Inneres, Digitalisierung und Sport - Drucksache 19/11840, 24.05.2022",
  "modified_at": "2022-05-31T12:51:25",
  "_file_name": "123fd201b54d7a6c91e6e9852008c3ad6698ffbe.data.pdf"
}
```

To import this file as "2022/05/Berlin/Beratungsvorgang/19-11840.pdf":

```bash
leakrfc -d my_dataset memorious sync -i /memorious/data/store/my_dataset --key-template "{{ date[:4] }}/{{ date[5:7] }}/{{ state }}/{{ category }}/{{ reference.replace('/','-') }}.{{ url.split('.')[-1] }}"
```

## Reference

::: leakrfc.sync.memorious

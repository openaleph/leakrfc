Sync a leakrfc dataset into an [Aleph](https://docs.aleph.occrp.org/) instance. This uses [alephclient](https://github.com/alephdata/alephclient/), so the configured `ALEPHCLIENT_API_KEY` needs to have the appropriate permissions.

Collections will be created if they don't exist and their metadata will be updated (this can be disabled via `--no-metadata`). The Aleph collections _foreign id_ can be set via `--foreign-id` and defaults to the leakrfc dataset name.

As long as using the global cache (environment `CACHE=1`, default) only new documents are synced. The cache handles multiple Aleph instances and keeps track of the individual status for each of them.

Aleph api configuration can as well set via command line:

```bash
leakrfc -d my_dataset aleph sync --host <host> --api-key <api-key>
```

Sync documents into a subfolder that will be created if it doesn't exist:

```bash
leakrfc -d my_dataset aleph sync --folder "Documents/Court cases"
```

## Reference

::: leakrfc.sync.aleph

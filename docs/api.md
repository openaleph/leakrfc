`leakrfc` provides a simpel api powered by [FastAPI](https://fastapi.tiangolo.com/) for clients to retrieve file metadata and blobs. It therefore acts as a proxy between client and archive, so that the client doesn't need to know where the actual blobs live. The api can handle authorization via [JSON Web Tokens](https://jwt.io).

## Installation

The API feature needs some extra packages that are not installed by default. Install `leakrfc` with api dependencies:

    pip install leakrfc[api]

## Start local api server

This is for a quick testing setup:

```bash
export LEAKRFC_URI=./data
uvicorn leakrfc.api:app
```

!!! warning

    Never run the api with `DEBUG=1` in a production application and make sure to have a proper setup with a load balancer (e.g. nginx) doing TLS termination in front of it. As well make sure to set a good `LEAKRFC_API_SECRET_KEY` environment variable for the token authorization.

## Request a file

For public files:

```bash
# metadata only via headers
curl -I "http://localhost:5000/test_dataset/utf.txt"

HTTP/1.1 200 OK
date: Thu, 16 Jan 2025 08:44:59 GMT
server: uvicorn
content-length: 4
content-type: application/json
x-leakrfc-version: 0.0.3
x-leakrfc-dataset: test_dataset
x-leakrfc-key: utf.txt
x-leakrfc-sha1: 5a6acf229ba576d9a40b09292595658bbb74ef56
x-leakrfc-name: utf.txt
x-leakrfc-size: 19
x-mimetype: text/plain
content-type: text/plain
```

```bash
# bytes stream of file
curl -s "http://localhost:5000/<dataset>/<path>" > /tmp/file.pdf
```

Authorization expects an encrypted bearer token with the dataset and key lookup in the subject (token payload: `{"sub": "<dataset>/<key>"}`). Therefore, clients need to be able to create such tokens (knowing the secret key configured via `LEAKRFC_API_SECRET_KEY`) and handle dataset permissions.

Tokens should have a short expiration (via `exp` property in payload).

```bash
# token in Authorization header
curl -H 'Authorization: Bearer <token>' ...

# metadata only via headers
curl -I "http://localhost:5000/file"

# bytes stream of file
curl -s "http://localhost:5000/file" > /tmp/file.lrfc
```

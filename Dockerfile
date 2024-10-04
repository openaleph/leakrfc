FROM python:3.12-bookworm

RUN apt-get -qq update && apt-get -qq -y upgrade
RUN apt-get install -qq -y pkg-config libicu-dev
RUN apt-get -qq -y autoremove && apt-get clean

RUN pip install --no-cache-dir -q -U pip setuptools

COPY leakrfc /src/leakrfc
COPY setup.py /src/setup.py
# COPY requirements.txt /src/requirements.txt
COPY README.md /src/README.md
COPY pyproject.toml /src/pyproject.toml
COPY VERSION /src/VERSION
COPY LICENSE /src/LICENSE
COPY NOTICE /src/NOTICE

WORKDIR /src
# RUN pip install -r requirements.txt
RUN pip install --no-cache-dir -q "."
RUN pip install --no-cache-dir -q -U redis sqlalchemy psycopg2-binary

ENTRYPOINT ["leakrfc"]

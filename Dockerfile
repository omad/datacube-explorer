# syntax=docker/dockerfile:1
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.3@sha256:dab45abca3ca83695d442018692f4f8a0f41955871c57e6101d7f89a92375caa AS base

LABEL org.opencontainers.image.source=https://github.com/opendatacube/datacube-explorer
LABEL org.opencontainers.image.description="Datacube Explorer"
LABEL org.opencontainers.image.licences="Apache-2.0"

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1


RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        git \
        # For shapely with --no-binary.
        libgeos-dev \
        libhdf5-dev \
        libnetcdf-dev \
        libudunits2-dev \
        # For psycopg2.
        libpq-dev \
        python3-dev \
    && mkdir /app \
    && chown ubuntu:ubuntu /app


# This cannot be inlined below (e.g., COPY --from=...) because Dependabot does not support that syntax yet
FROM ghcr.io/astral-sh/uv:0.9.9@sha256:f6e3549ed287fee0ddde2460a2a74a2d74366f84b04aaa34c1f19fec40da8652 AS uv

FROM base AS builder

WORKDIR /build

COPY --link pyproject.toml uv.lock /build/

# Install Dependencies into venv in /app
RUN --mount=type=cache,id=opendatacube-uv-cache,target=/root/.cache \
    --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    export SETUPTOOLS_SCM_DEBUG=1 && \
    echo $SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DATACUBE_EXPLORER && \
    uv sync --frozen \
      --extra=deployment \
      --no-install-project \
      --no-group dev \
      --no-binary-package fiona \
      --no-binary-package netcdf4 \
      --no-binary-package psycopg2 \
      --no-binary-package rasterio \
      --no-binary-package shapely

COPY --link . /build/

# Install dev dependencies, and the project itself in editable mode from /build
FROM builder AS dev

ARG DATACUBE_EXPLORER_VERSION=0.0.0.dev0
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DATACUBE_EXPLORER=$DATACUBE_EXPLORER_VERSION
COPY --link --from=uv /uv /uvx /usr/local/bin/
RUN --mount=type=cache,id=opendatacube-uv-cache,target=/root/.cache \
    uv sync --frozen --all-extras --all-groups


FROM builder AS prod

COPY --from=builder --link --chown=1000:1000 /app /app

ARG DATACUBE_EXPLORER_VERSION=0.0.0.dev0
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DATACUBE_EXPLORER=$DATACUBE_EXPLORER_VERSION
ARG FOO=bar
RUN set -e; \
    if [ "${SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DATACUBE_EXPLORER}" = "0.0.0.dev0" ]; then \
        echo "To Build a Production Datacube Explorer Image either use 'make docker' or" && \
        echo 'specify `docker build --arg DATACUBE_EXPLORER_VERSION=$(uvx setuptools-scm)` as part ' && \
        echo "of the docker build options." && \
        exit 1; \
    fi

# RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    

# Configure user
WORKDIR "/home/ubuntu"
USER ubuntu:ubuntu

ENV PATH=/app/bin:$PATH

# This is for prod, and serves as docs. It's usually overwritten
CMD ["gunicorn", \
     "-b", \
     "0.0.0.0:8080", \
     "-w", \
     "3", \
     "--threads=2", \
     "-k", \
     "gthread", \
     "--timeout", \
     "90", \
     "--config", \
     "python:cubedash.gunicorn_config", \
     "cubedash:create_app()"]

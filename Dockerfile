# syntax=docker/dockerfile:1
#
# TopoLogic: the API and the models it serves, in one image, run by an unprivileged uid on
# a read-only root filesystem. See docker_containers_update/topologic/MIGRATION.md.
#
# This image *serves* models; it does not build them. A model is trained elsewhere and its
# directory — model.duckdb, dist/, appConfig.json, model_config.ini, topic_words.json — is
# copied onto the host and bind-mounted read-only. So there is no torch, no CUDA, no spaCy,
# no BERTopic, no Node and no PhiloLogic here: see requirements.txt for what was dropped
# and why. The previous image was 8.11 GB, of which 4.8 GB was GPU torch on a host with no
# GPU, and it carried a PostgreSQL server that upstream has since replaced with DuckDB.

# ---- builder: compiles annoy, then never ships ----
# annoy publishes no Linux wheel for any Python version (only macOS arm64), so it is
# compiled from its sdist and that needs a C++ toolchain. Keeping the toolchain in a
# separate stage is the whole reason this build has two: g++, its headers and the uv cache
# stay here, and the runtime stage below copies only the finished interpreter and venv.
FROM ubuntu:26.04 AS build
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
ARG REBUILD_DATE=unset
RUN echo "rebuild: $REBUILD_DATE" \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates g++ \
 && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY requirements.txt /tmp/requirements.txt
RUN uv venv /opt/venv --python 3.13 --managed-python \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r /tmp/requirements.txt \
 # uv's CPython ships pip, which vendors its own setuptools and msgpack. Nothing here
 # installs anything at runtime - the venv is built in this stage, once - so the weekly
 # scan would report findings against them that could never be actioned. Same removal as
 # commonplaces and philologic5.
 && rm -rf /opt/python/cpython-*/lib/python3.13/site-packages/pip \
           /opt/python/cpython-*/lib/python3.13/site-packages/pip-*.dist-info \
           /opt/python/cpython-*/lib/python3.13/ensurepip/_bundled/pip-*.whl

# The topologic package itself, with --no-deps: its pyproject declares the *training*
# dependency set, and resolving it would drag back everything requirements.txt exists to
# exclude. What the API imports from it is read_config and DB.DBSearch.
COPY lib /tmp/lib
RUN VIRTUAL_ENV=/opt/venv uv pip install --no-cache --no-deps /tmp/lib

# ---- runtime ----
FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

# Busted weekly by the build arg so that a weekly rebuild actually applies security updates
# instead of reusing a cached layer (CONTAINER_UPDATE_PLAN.md 5.1).
ARG REBUILD_DATE=unset
RUN echo "rebuild: $REBUILD_DATE" \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 # Canonical's base image ships /usr/bin/pebble, their service manager for OCI images.
 # Nothing here uses it — the entrypoint starts gunicorn directly — and it is a 10 MB Go
 # binary that carried 8 HIGH CVEs on the first weekly scan of the dvlf image, 2026-09-07.
 && rm -f /usr/bin/pebble

# 481 is deliberate and matches a real `topologic` system account on the host, so the
# bind-mounted model directory and the container's processes read as `topologic` on both
# sides. Same pattern as dvlf (480) and artfl-platform-services (358). The obvious choice,
# 999, is systemd-coredump on the host, which makes `ls -l` and `ps` actively misleading.
RUN groupadd -g 481 topologic && useradd -u 481 -g 481 -M -s /usr/sbin/nologin topologic

# The interpreter comes from uv rather than the distro, so it is pinned in the builder
# stage and bumped as a deliberate decision instead of moving with the base image. Only
# the finished interpreter and venv cross over — no uv, no compiler, no caches.
COPY --from=build /opt/python /opt/python
COPY --from=build /opt/venv /opt/venv

# HOME=/tmp because gunicorn 26's control server opens a socket under $HOME, and this uid
# has no home directory — deliberately, it is a service account. Without this the master
# logs "Control server error: Permission denied: '/home/topologic'" on every start, and on
# a read-only root filesystem there is nowhere else for it to go. /tmp is the tmpfs.
ENV PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/mpl

# gunicorn --chdir here; the app reads /etc/topologic/global_settings.ini for the one key
# it needs (WEB_APP.web_app_path) and everything else from the model directory.
COPY api/topologic_explorer.py /var/lib/topologic/api/
COPY entrypoint.sh /entrypoint.sh

USER 481:481
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

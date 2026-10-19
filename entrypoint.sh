#!/bin/sh
# TopoLogic deployment entrypoint: one process, no database server.
#
# The model is a DuckDB file on a read-only bind mount, opened read_only=True by each
# worker, so there is nothing to start, supervise or shut down cleanly. That is the whole
# difference from the container this replaces, which ran PostgreSQL beside the app.
set -e

# Bind :8000 — all interfaces *inside the container*. It is the compose file's
# `127.0.0.1:8450:8000` that keeps this off-host: Docker DNATs published ports to the
# container's bridge address, so binding the container's own loopback here would make the
# published port unreachable rather than more secure.
#
# The flags below deliberately replace api_server/gunicorn.conf.py rather than editing it:
# that file binds :8080 and writes access.log and error.log into the image. Logs go to
# stdout so the compose file's max-size can cap them; nothing in the repo is modified.
exec gunicorn topologic_explorer:app \
    --chdir /var/lib/topologic/api \
    -b :8000 \
    -w "${TOPOLOGIC_WORKERS:-4}" \
    -k uvicorn.workers.UvicornWorker \
    --worker-tmp-dir /tmp \
    --access-logfile - \
    --error-logfile -

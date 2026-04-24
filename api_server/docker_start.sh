#!/bin/bash
# Entrypoint for the Docker image: runs gunicorn on :80 serving the bundled
# app (SPA static + API, both under their external prefixes). No reverse
# proxy is expected in front of this.
set -e
source /var/lib/topologic/topologic_env/bin/activate
cd /var/lib/topologic/api/
exec gunicorn topologic_bundled:app \
    -b :80 \
    -w "${TOPOLOGIC_WORKERS:-4}" \
    -k uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile -

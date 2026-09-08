"""Single-port bundled app for Docker / standalone gunicorn deployments.

The manual-install layout expects a reverse proxy (apache, nginx) to strip
path prefixes before forwarding to the API, so `topologic_explorer:app`
registers its routes at the bare paths (`/get_topic_data/...`, `/{db}/topic/...`).

In the Docker image we run gunicorn directly on :80 with no upstream proxy,
so the request paths arrive un-stripped. This wrapper mounts the same app
twice — once at each external prefix — so:
    /topologic-api/get_topic_data/...  ->  /get_topic_data/...
    /topologic/{db}/topic/...          ->  /{db}/topic/...
both reach the right handlers.
"""
from fastapi import FastAPI

from topologic_explorer import app as base_app

app = FastAPI()
# Order matters: the longer prefix must be registered first so
# `/topologic-api/...` is not captured by the `/topologic` mount.
app.mount("/topologic-api", base_app)
app.mount("/topologic", base_app)

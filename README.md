# TopoLogic

Yet Another Topic Modeling Browser...

Originally based off https://github.com/AdrienGuille/TOM with many changes and enhancements. Each trained model is stored as a DuckDB file served by the bundled API.

## INSTALLATION

While you can build and install TopoLogic directly, it is highly encouraged to use a Docker container instead.

### Docker install
- Run `docker build -t topologic .` to build the image (CUDA-enabled by default). For a CPU-only image, pass `--build-arg TOPOLOGIC_BACKEND=cpu`.
- Run `docker run -td --name topologic -p 8080:80 topologic` to start the container. The image listens on port 80 internally (gunicorn serves the SPA and the API on a single port); map it to whatever host port you like.
- Enter the container with `docker exec -it topologic bash`.
- If you need to install SpaCy models, enter the topologic virtual environment first: `source /var/lib/topologic/topologic_env/bin/activate`.
- If you are exposing the container at a hostname other than `localhost`, edit `/etc/topologic/global_settings.ini` inside the container (or mount a replacement in) and set `server_name` to that hostname before training. The value is baked into each model's `appConfig.json` at training time so the frontend knows where to reach the API.


### Manual installation
-   Edit `/etc/topologic/global_settings.ini` with the web configuration. No separate database server to configure — each trained model is stored as a DuckDB file under its web-app directory.
-   Run the `install.sh` script (it will install [uv](https://docs.astral.sh/uv/getting-started/installation/) automatically if it isn't already on your system; uv then manages Python 3.12 and the project virtual environment). Pass `--cpu` or `--cuda` to pick the torch backend; without a flag, the script auto-detects via `nvidia-smi`.
-   If your OS uses systemd, use the `topologic.service` template in `api_server/topologic.service` to start the API server.
-   The install includes Gunicorn, used to serve the API. Start it from the shell script installed in `/var/lib/topologic/api_server/`, adjusting paths/ports for your setup.
-   **Re-running `install.sh` restarts the API server** if `topologic.service` is installed *and* currently running — Gunicorn loads the API module at worker start, so without a restart the install looks like it did nothing. A service that is installed but stopped is left stopped, and a server running outside systemd is reported rather than touched. Pass `--no-restart` to skip.


## HOW TO USE

-   Copy `topologic_config.ini` from `/var/lib/topologic/config` to your working directory and edit it.
-   Run the `topologic` executable, passing the config and the number of workers. E.g.

    `topologic --config=topologic_config.ini --workers=32`

### Per-deployment configuration

Each trained model emits two config files next to the web app:

- `appConfig.build.json` — values Vite bakes into the bundle (just the deployment path). Editing requires a rebuild.
- `appConfig.json` — runtime config fetched by the browser on page load: API server URL, display name, metadata fields to show, per-DB citation styling, time-series bounds. Edits take effect on page reload, no rebuild needed.

### NOTE

If you run out of memory when processing the text files, use fewer cores. This lowers the chance of data accumulating in RAM while waiting to be written out to disk.

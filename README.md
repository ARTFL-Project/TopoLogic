# TopoLogic

Yet Another Topic Modeling Browser...

Originally based off https://github.com/AdrienGuille/TOM with many changes and enhancements. Each trained model is stored as a DuckDB file served by the bundled API.

## INSTALLATION

While you can build and install TopoLogic directly, it is highly encouraged to use a Docker container instead.

### Docker install
- Run `docker build -t topologic .` to build the image.
- Run `docker run -td --name topologic topologic init_topologic` to initialize the container. You may want to specify ports for web passthrough (e.g. `-p 8080:80` to map port 8080 on the host to port 80 on the container).
- Enter the container with `docker exec -it topologic bash`.
- If you need to install SpaCy models, enter the topologic virtual environment first: `source /var/lib/topologic/topologic_env/bin/activate`.


### Manual installation
-   Edit `/etc/topologic/global_settings.ini` with the web configuration. No separate database server to configure — each trained model is stored as a DuckDB file under its web-app directory.
-   Run the `install.sh` script (it will install [uv](https://docs.astral.sh/uv/getting-started/installation/) automatically if it isn't already on your system; uv then manages Python 3.12 and the project virtual environment).
-   If your OS uses systemd, use the `topologic.service` template in `api_server/topologic.service` to start the API server.
-   The install includes Gunicorn, used to serve the API. Start it from the shell script installed in `/var/lib/topologic/api_server/`, adjusting paths/ports for your setup.


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

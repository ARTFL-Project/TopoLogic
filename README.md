# TopoLogic

Yet Another Topic Modeling Browser...

Originally based off https://github.com/AdrienGuille/TOM with many changes and enhancements and tied to PhiloLogic

## INSTALLATION

While you can build and install TopoLogic directly, it is highly encouraged to use a Docker container instead.

### Docker install
Note that the docker container will come with PhiloLogic 4.7 pre-installed. You will need to build PhiloLogic databases within the container before running TopoLogic
- Just run `docker build -t topologic .` to build the image
- Then run `docker run -td --name topologic topologic init_topologic` to initialize the container. You may want to specify ports for web passthrough (e.g. `-p 8080:80` to map port 8080 on the host to port 80 on the container)
- Once the container is running, enter the container with `docker exec -it topologic bash`.
- Note that if you need to install SpaCy models, you will need to enter the topologic virtual environment like so: `source /var/lib/topologic/topologic_env/bin/activate`


### Manual installation
-   You will need to edit the /etc/topologic/global_settings.ini file with the web configuration (no database server to configure — storage is a per-model DuckDB file under the web app directory).
-   You will need a running instance of <a href="https://github.com/ARTFL-Project/PhiloLogic4">PhiloLogic4</a> with the collections to be processed already loaded.
-   Run the install.sh script (it will install [uv](https://docs.astral.sh/uv/getting-started/installation/) automatically if it isn't already on your system; uv then manages Python 3.12 and the project virtual environment)
-   If you OS uses systemd for start-up services, you will want to use the topologic.service file (template for Ubuntu provided as an example) located in api_server/topologic.service to start-up the API server needed to run Topologic
-  The installation includes the Gunicorn webserver which is used to run the TopoLogic web app. You will need to start the server from a shell script installed in /var/lib/topologic/api_server/. This wil require some configuring in the shell script depending on your setup.


## HOW TO USE

-   Make a copy of the topologic_config.ini file found in /var/lib/topologic/config to your working directory, Edit the topologic_config.ini accordingly.
-   Use the topologic executable while passing the config and the number of workers to use. E.g.

`topologic --config=topologic_config.ini --workers=32`

### NOTE

If you run out of memory when processing the text files, use fewer cores. This will lower the chance the data accumulates in RAM while waiting to be written out to disk.

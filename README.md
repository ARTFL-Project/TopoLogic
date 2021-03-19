# TopoLogic

Yet Another Topic Modeling Browser...

Originally based off https://github.com/AdrienGuille/TOM with many changes and enhancements and tied to PhiloLogic

## INSTALLATION

-   PostgreSQL will need to be installed. You will need to create a database with associated user with read and write permissions.
-   You will need to edit the /etc/topologic/global_settings.ini file with the database information and web configuration.
-   You will need a running instance of <a href="https://github.com/ARTFL-Project/PhiloLogic4">PhiloLogic4</a> with the collections to be processed already loaded.
-   Run the install.sh script
-   If you OS uses systemd for start-up services, you will want to use the topologic.service file (template for Ubuntu provided as an example) located in api_server/topologic.service to start-up the API server needed to run Topologic
-  The installation includes the Gunicorn webserver which is used to run the TopoLogic web app. You will need to start the server from a shell script installed in /etc/topologic/api_server/. This wil require some configuring in the shell script depending on your setup. 


## HOW TO USE

-   Make a copy of the topologic_config.ini file found in /var/lib/topic-modeling-browser/config to your working directory, Edit the topic_modeling_browser_config.ini accordingly.
-   Use the topic_modeling_browser executable while passing the config and the number of workers to use. E.g.

`TopoLogic --config=topologic_config.ini --workers=32`

### NOTE

If you run out of memory when processing the text files, use fewer cores. This will lower the chance the data accumulates in RAM while waiting to be written out to disk.

#!/bin/bash

source /var/lib/topologic/lib/.venv/bin/activate

# Start Gunicorn with the configuration file
gunicorn topologic_explorer:app -c /var/lib/topologic/api_server/gunicorn.conf.py

#!/bin/bash

# Ensure uv is installed — https://docs.astral.sh/uv/getting-started/installation/
if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install it first with:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Give current user permission to write to /var/lib/topologic
sudo mkdir -p /var/lib/topologic
sudo chown -R $USER:$USER /var/lib/topologic

# Install a uv-managed Python 3.12 and create the virtual environment
uv python install 3.12
uv venv --python 3.12 /var/lib/topologic/topologic_env
uv pip install --python /var/lib/topologic/topologic_env/bin/python --upgrade lib/.

# Install the topologic script
sudo cp topologic /usr/local/bin/
sudo chmod +x /usr/local/bin/topologic

echo -e "\nMoving web application components into place..."

if [ ! -f /etc/topologic/global_settings.ini ]
    then
        sudo mkdir -p /etc/topologic/
        cp config/global_settings.ini /etc/topologic/
        echo "Make sure you create a PostgreSQL database with a user with read/write access to that database and configure /etc/topologic/global_settings.ini accordingly."
else
    echo "/etc/topologic/global_settings.ini already exists, not modifying..."
fi

sudo mkdir -p /var/lib/topologic/api_server/
sudo chown -R $USER:$USER /var/lib/topologic/api_server
cp api_server/web_server.sh /var/lib/topologic/api_server/
if [ ! -f /var/lib/topologic/api_server/gunicorn.conf.py ]
    then
        cp api_server/gunicorn.conf.py /var/lib/topologic/api_server/
else
    echo "/var/lib/topologic/api_server/gunicorn.conf.py already exists, not modifying..."
fi

cp -R api /var/lib/topologic/
rm -rf /var/lib/topologic/web-app
cp -Rf web-app /var/lib/topologic
sudo rm -rf /var/lib/topologic/web_app/node_modules
sudo rm -rf /var/lib/topologic/web_app/dist
rm -rf /var/lib/topologic/config
cp -Rf config /var/lib/topologic
echo -e "\n## IMPORTANT ##\nTopoLogic runs behind the Gunicorn web server. Make sure you configure the Gunicorn config file in /var/lib/topologic/api_server/gunicorn.conf.py. You should also make sure it autostarts on boot.\n"
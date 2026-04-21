#!/bin/bash

# Ensure uv is installed — https://docs.astral.sh/uv/getting-started/installation/
# uv is only needed during this install script; the runtime wrappers activate
# the venv directly, so they don't need uv on PATH.
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — installing via the official installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer drops uv at ~/.local/bin/uv but does not touch the
    # current shell's PATH, so add it explicitly for the rest of this script.
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv installation failed. See https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

# Give current user permission to write to /var/lib/topologic
sudo mkdir -p /var/lib/topologic
sudo chown -R $USER:$USER /var/lib/topologic

# Install a uv-managed Python 3.12
uv python install 3.12

# Copy the Python project (pyproject.toml + uv.lock + topologic package) into place,
# then sync the venv from the lockfile. The venv lives at /var/lib/topologic/lib/.venv.
rm -rf /var/lib/topologic/lib
cp -R lib /var/lib/topologic/lib
( cd /var/lib/topologic/lib && uv sync --frozen )

# Install the topologic script
sudo cp topologic /usr/local/bin/
sudo chmod +x /usr/local/bin/topologic

echo -e "\nMoving web application components into place..."

if [ ! -f /etc/topologic/global_settings.ini ]
    then
        sudo mkdir -p /etc/topologic/
        sudo cp config/global_settings.ini /etc/topologic/
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
# Copy everything except node_modules and the pre-built dist; the dist is
# regenerated per-deployment by the topologic CLI (which writes appConfig.json
# and then runs `npm install && npm run build` in the target directory).
rsync -a --exclude node_modules --exclude dist web-app/ /var/lib/topologic/web-app/
rm -rf /var/lib/topologic/config
cp -Rf config /var/lib/topologic
echo -e "\n## IMPORTANT ##\nTopoLogic runs behind the Gunicorn web server. Make sure you configure the Gunicorn config file in /var/lib/topologic/api_server/gunicorn.conf.py. You should also make sure it autostarts on boot.\n"
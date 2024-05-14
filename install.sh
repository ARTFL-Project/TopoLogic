#!/bin/bash

# Install virtualenv to sidestep venv (python3-venv installs python3-setuptools which causes issues on Ubuntu 22.04)
pip3 install virtualenv

# Give current user permission to write to /var/lib/topologic
sudo mkdir -p /var/lib/topologic
sudo chown -R $USER:$USER /var/lib/topologic

# Create the virtual environment
virtualenv /var/lib/topologic/topologic_env
source /var/lib/topologic/topologic_env/bin/activate
pip3 install lib/. --upgrade --use-pep517
deactivate

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





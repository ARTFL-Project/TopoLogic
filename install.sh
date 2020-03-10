#!/bin/sh

sudo pip3 install lib/. --upgrade


echo "\nMoving web application components into place..."
sudo mkdir -p /var/lib/topologic


if [ -d /web-app/browser-app/node_modules ]
    then
        sudo rm -rf web/web_app/node_modules
fi

if [ ! -f /etc/topologic/global_settings.ini ]
    then
        sudo touch /etc/topologic/global_settings.ini
        echo "## WEB APPLICATION SETTINGS ##" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "[WEB_APP]" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "web_app_path =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "server_name =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "[DATABASE]" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "database_name =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "database_user =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "database_password =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "Make sure you create a PostgreSQL database with a user with read/write access to that database and configure /etc/topologic/global_settings.ini accordingly."
else
    echo "/etc/topologic/global_settings.ini already exists, not modifying..."
fi

if [ ! -f /var/lib/topologic/api_server/web_server.sh ]
    then
        sudo cp -R api_server /var/lib/topologic/
else
    echo "/var/lib/topologic/api_server/web_server.sh already exists, not modifying..."
fi

sudo cp -R api /var/lib/topologic/
sudo rm -rf /var/lib/topologic/web-app
sudo cp -Rf web-app /var/lib/topologic
sudo rm -rf /var/lib/topologic/config
sudo cp -Rf config /var/lib/topologic
echo "\n## IMPORTANT ##\nTopoLogic runs behind the Gunicorn web server. Make sure you configure the server start script at /var/lib/topologic/web-app/api/web_app_start.sh. You should also make sure it autostarts on boot.\n"





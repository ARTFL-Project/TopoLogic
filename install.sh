#!/bin/sh

sudo pip3 install lib/. --upgrade


echo "\nMoving web application components into place..."
sudo rm -rf /var/lib/topologic
sudo mkdir -p /var/lib/topologic


if [ -d /web-app/browser-app/node_modules ]
    then
        sudo rm -rf web/web_app/node_modules
fi

sudo cp -Rf web-app /var/lib/topologic
sudo cp -Rf config /var/lib/topologic

echo "\nMoving global configuration into place..."
sudo mkdir -p /etc/topologic
if [ ! -f /etc/topologic/apache_wsgi.conf ]
    then
        sudo cp -R web-app/apache_wsgi.conf /etc/topologic
        echo "\nMake sure you include /etc/topologic/apache_wsgi.conf in your main Apache configuration file in order to enable searching through the web app."
else
    echo "/etc/topologic/apache_wsgi.conf already exists, not modifying..."
fi

if [ ! -f /etc/topologic/global_settings.ini ]
    then
        sudo touch /etc/topologic/global_settings.ini
        echo "## WEB APPLICATION SETTINGS ##" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "[WEB_APP]" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "web_app_path =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "apiServer = http://localhost/topologic-api/" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "[DATABASE]" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "database_name =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "database_user =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "database_password =" | sudo tee -a /etc/topologic/global_settings.ini > /dev/null
        echo "Make sure you create a PostgreSQL database with a user with read/write access to that database and configure /etc/topologic/global_settings.ini accordingly."
else
    echo "/etc/topologic/global_settings.ini already exists, not modifying..."
fi



#!/bin/sh

sudo pip3 install lib/. --upgrade


echo "\nMoving web application components into place..."
sudo rm -rf /var/lib/topic-modeling-browser
sudo mkdir -p /var/lib/topic-modeling-browser


if [ -d /web-app/browser-app/node_modules ]
    then
        sudo rm -rf web/web_app/node_modules
fi

sudo cp -Rf web-app /var/lib/topic-modeling-browser
# sudo cp -Rf config /var/lib/topic-modeling-browser

echo "\nMoving global configuration into place..."
sudo mkdir -p /etc/topic-modeling-browser
if [ ! -f /etc/topic-modeling-browser/apache_wsgi.conf ]
    then
        sudo cp -R web-app/apache_wsgi.conf /etc/topic-modeling-browser
        echo "\nMake sure you include /etc/topic-modeling-browser/apache_wsgi.conf in your main Apache configuration file in order to enable searching through the web app."
else
    echo "/etc/topic-modeling-browser/apache_wsgi.conf already exists, not modifying..."
fi

if [ ! -f /etc/topic-modeling-browser/global_settings.ini ]
    then
        sudo touch /etc/topic-modeling-browser/global_settings.ini
        echo "## WEB APPLICATION SETTINGS ##" | sudo tee -a /etc/topic-modeling-browser/global_settings.ini > /dev/null
        echo "[WEB_APP]" | sudo tee -a /etc/topic-modeling-browser/global_settings.ini > /dev/null
        echo "web_app_path =" | sudo tee -a /etc/topic-modeling-browser/global_settings.ini > /dev/null
else
    echo "/etc/topic-modeling-browser/global_settings.ini already exists, not modifying..."
fi



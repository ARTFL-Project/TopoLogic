FROM artfl/philologic:latest

RUN apt update && apt install -y postgresql postgresql-contrib postgresql-server-dev-12 apache2-dev curl git locales

RUN curl -sL https://deb.nodesource.com/setup_14.x | sudo -E bash && apt-get install -y nodejs

RUN apt-get clean && rm -rf /var/lib/apt

RUN mkdir topologic && curl -L  https://github.com/ARTFL-Project/TopoLogic/archive/refs/tags/v0.3.tar.gz | tar xz -C topologic --strip-components 1 &&\
    cd topologic && sh install.sh

RUN perl -p -i -e 's/(<\/VirtualHost>)/<Location \/topologic-api>\nProxyPass http:\/\/localhost:8080 Keepalive=On\nProxyPassReverse http:\/\/localhost:8080\n<\/Location>\n$1/' /etc/apache2/sites-enabled/000-default.conf

RUN echo "## WEB APPLICATION SETTINGS ##\n[WEB_APP]\nweb_app_path = /var/www/html/topologic\nserver_name = http://localhost/\n[DATABASE]\ndatabase_name = topologic\ndatabase_user = topologic\ndatabase_password = topologic" > /etc/topologic/global_settings.ini

# Set the locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

RUN echo "#!/bin/bash\nif [ ! -d \"/data/psql_data\" ]; then\nsu postgres <<'EOF'\n/usr/lib/postgresql/12/bin/initdb --pgdata=/data/psql_data;\ncd /data/psql_data\n/usr/lib/postgresql/12/bin/pg_ctl -D /data/psql_data/ -l logfile start\npsql -c \"create database\ntopologic ENCODING = 'UTF8' LC_COLLATE = 'en_US.UTF-8' LC_CTYPE = 'en_US.UTF-8';\"\npsql -c \"create role topologic with login password 'topologic';\"\npsql -c \"GRANT ALL PRIVILEGES ON database topologic to topologic;\"\nEOF\nperl -pi -e 's/^(local.*)peer$/$1md5/;' /data/psql_data/pg_hba.conf\nsu postgres <<'EOF'\ncd /data/psql_data\n/usr/lib/postgresql/12/bin/pg_ctl -D /data/psql_data/ -l logfile restart\nEOF\nmkdir /data/topologic && ln -s /data/topologic /var/www/html/topologic\nelse\nsu postgres <<'EOF'\ncd /data/psql_data\n/usr/lib/postgresql/12/bin/pg_ctl -D /data/psql_data/ -l logfile restart\nEOF\nln -s /data/topologic /var/www/html/topologic\nfi\napachectl start\n/var/lib/topologic/api_server/web_server.sh &\n/bin/bash" > /usr/local/bin/init_topologic_db && chmod +x /usr/local/bin/init_topologic_db

CMD ["/usr/local/bin/init_topologic_db"]

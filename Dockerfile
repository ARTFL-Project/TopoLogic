FROM artfl/philologic:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y postgresql postgresql-contrib postgresql-server-dev-14 locales git g++

RUN apt-get clean && rm -rf /var/lib/apt

RUN service apache2 start && a2enmod proxy && a2enmod proxy_http && service apache2 stop

RUN mkdir topologic
COPY api /topologic/api
COPY api_server /topologic/api_server
COPY lib /topologic/lib
COPY web-app /topologic/web-app
COPY config /topologic/config
COPY init_topologic /topologic/init_topologic
COPY topologic /topologic/topologic
COPY install.sh /topologic/install.sh

RUN cd /topologic && ./install.sh
RUN mkdir /var/www/html/topologic
COPY init_topologic /usr/local/bin/init_topologic
RUN chmod +x /usr/local/bin/init_topologic

# Set the locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

RUN perl -pi -e 's/^(local.*)peer$/$1md5/;' /etc/postgresql/14/main/pg_hba.conf
RUN echo "local all all trust" > /etc/postgresql/14/main/pg_hba.conf && \
    echo "host all all 127.0.0.1/32 trust" >> /etc/postgresql/14/main/pg_hba.conf && \
    echo "host all all ::1/128 trust" >> /etc/postgresql/14/main/pg_hba.conf
RUN service postgresql start && \
    su postgres -c "psql -c \"CREATE DATABASE topologic ENCODING = 'UTF8' LC_COLLATE = 'en_US.UTF-8' LC_CTYPE = 'en_US.UTF-8' TEMPLATE template0;\"" && \
    su postgres -c 'psql -c "create role topologic with login password '\''topologic'\'';"' && \
    su postgres -c 'psql -c "GRANT ALL PRIVILEGES ON database topologic to topologic;"'
RUN service postgresql restart

CMD ["/usr/local/bin/init_topologic"]
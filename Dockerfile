FROM artfl/philologic:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt remove -y nodejs libnode72 libnode-dev && apt install curl

RUN curl -sL https://deb.nodesource.com/setup_18.x | sudo -E bash -

RUN apt update && apt install -y locales git g++ nodejs

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

CMD ["/usr/local/bin/init_topologic"]

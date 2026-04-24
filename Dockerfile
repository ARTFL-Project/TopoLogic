FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Base tools needed during install + runtime.
# - curl: uv installer, nodesource setup
# - git, g++: wheel builds (annoy) and the text-preprocessing git source
# - sudo: install.sh uses it to seed /var/lib/topologic
# - locales: en_US.UTF-8 for consistent text handling
# - ca-certificates: HTTPS for pip/uv/npm downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git g++ rsync ca-certificates locales sudo \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# Node 18+ for per-deployment `npm run build` (the topologic CLI invokes
# this after writing appConfig.build.json into each model's dir).
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /topologic
COPY api /topologic/api
COPY api_server /topologic/api_server
COPY lib /topologic/lib
COPY labeler /topologic/labeler
COPY web-app /topologic/web-app
COPY config /topologic/config
COPY topologic /topologic/topologic
COPY install.sh /topologic/install.sh

# Default to the CUDA backend inside the image (nvidia-smi isn't available at
# build time, so auto-detection would silently pick CPU). Override with
# `--build-arg TOPOLOGIC_BACKEND=cpu` for a CPU-only image.
ARG TOPOLOGIC_BACKEND=cuda
RUN cd /topologic && ./install.sh --${TOPOLOGIC_BACKEND}

RUN mkdir -p /var/www/html/topologic \
    && chmod +x /topologic/api_server/docker_start.sh \
    && cp /topologic/api_server/docker_start.sh /var/lib/topologic/api_server/docker_start.sh

EXPOSE 80

CMD ["/var/lib/topologic/api_server/docker_start.sh"]

#####################
# BUILD ENVIRONMENT #
#####################

FROM golang:alpine AS build_chia_exporter

WORKDIR /build

RUN apk add --update --no-cache --virtual build-dependencies git ca-certificates && \
    git clone --depth 1 -b 0.11.1 https://github.com/Chia-Network/chia-exporter.git && \
    cd chia-exporter && \
    go build -o chia_exporter

#####################
# FINAL ENVIRONMENT #
#####################

FROM debian:stable-slim

LABEL maintainer="contact@openchia.io"

RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y git python3-virtualenv lsb-release sudo procps tmux net-tools vim iputils-ping netcat-traditional

WORKDIR /root
COPY . /root/chia-blockchain

WORKDIR /root/chia-blockchain
RUN sh install.sh

WORKDIR /root/chia-exporter
COPY --from=build_chia_exporter /build/chia-exporter/chia_exporter .

# Expose RPC ports
EXPOSE 58444
EXPOSE 8444
EXPOSE 8555
EXPOSE 9256
# Chia prometheus exporter
EXPOSE 9914

COPY ./docker/start.sh /root/start.sh
COPY ./docker/change_config.py /root/change_config.py

ENV PATH=/root/chia-blockchain/venv/bin:$PATH

CMD ["bash", "/root/start.sh"]

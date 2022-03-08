FROM debian:stable

# Identify the maintainer of an image
LABEL maintainer="contact@openchia.io"

# Update the image to the latest packages
RUN apt-get update && apt-get upgrade -y

# Install git
RUN apt-get install git python3-virtualenv lsb-release sudo procps tmux net-tools vim iputils-ping netcat golang -y

WORKDIR /root

RUN git clone --depth 1 -b v0.5.2 https://github.com/retzkek/chia_exporter.git && \
  cd chia_exporter && go build

COPY . /root/chia-blockchain

WORKDIR /root/chia-blockchain

RUN sh install.sh

# Expose RPC ports
EXPOSE 58444
EXPOSE 8444
EXPOSE 8555
EXPOSE 9256
# Chia prometheus exporter
EXPOSE 9133

COPY ./docker/start.sh /root/start.sh
COPY ./docker/change_config.py /root/change_config.py

ENV PATH=/root/chia-blockchain/venv/bin:$PATH

CMD ["bash", "/root/start.sh"]

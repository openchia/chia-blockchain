FROM debian:stable

# Identify the maintainer of an image
LABEL maintainer="contact@openchia.io"

# Update the image to the latest packages
RUN apt-get update && apt-get upgrade -y

# Install git
RUN apt-get install git python3-virtualenv lsb-release sudo procps tmux net-tools vim iputils-ping netcat -y

COPY . /root/chia-blockchain

WORKDIR /root/chia-blockchain

RUN sh install.sh

# Expose RPC ports
EXPOSE 8444
EXPOSE 8555
EXPOSE 9256

COPY ./docker/start.sh /root/start.sh
COPY ./docker/change_config.py /root/change_config.py

ENV PATH=/root/chia-blockchain/venv/bin:$PATH

CMD ["bash", "/root/start.sh"]

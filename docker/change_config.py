#!/usr/bin/env python3
import os
import yaml

CONFIG_PATH = '/root/.chia/mainnet/config/config.yaml'


def main():
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)

    chia_network = os.environ.get('CHIA_NETWORK', 'mainnet')
    if 'testnet' in chia_network:
        default_node_port = 58444
    else:
        default_node_port = 8444

    config['self_hostname'] = '0.0.0.0'
    config['wallet']['full_node_peer']['host'] = os.environ.get('CHIA_NODE_HOST', 'localhost')
    config['wallet']['full_node_peer']['port'] = int(os.environ.get('CHIA_NODE_PORT', default_node_port))
    config['wallet']['trusted_peers']['trusted_node_1'] = os.environ.get('CHIA_NODE_CRT', f'/data/chia/{chia_network}/config/ssl/full_node/public_full_node.crt')

    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)


if __name__ == '__main__':
    main()

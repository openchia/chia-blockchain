#!/usr/bin/env python3
import os
import yaml

CONFIG_PATH = '/root/.chia/mainnet/config/config.yaml'


def main():
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)

    chia_network = os.environ.get('CHIA_NETWORK', 'mainnet')

    log_level = os.environ.get('CHIA_LOGLEVEL', 'WARNING')
    config['farmer']['logging']['log_level'] = log_level

    multiprocessing_method = os.environ.get('CHIA_MULTIPROCESSING_METHOD', 'default')
    config['wallet']['multiprocessing_start_method'] = multiprocessing_method

    trusted_node_id = os.environ.get('CHIA_TRUSTED_NODEID') or 'trusted_node_1'

    config['self_hostname'] = '0.0.0.0'

    node_host = os.environ.get('CHIA_NODE_HOST')
    if node_host:
        if 'testnet' in chia_network:
            default_node_port = 58444
        else:
            default_node_port = 8444

        config['wallet']['full_node_peer']['host'] = node_host
        config['wallet']['full_node_peer']['port'] = int(os.environ.get('CHIA_NODE_PORT', default_node_port))
    else:
        config['wallet'].pop('full_node_peer', None)
    config['wallet']['trusted_peers'][trusted_node_id] = os.environ.get('CHIA_NODE_CRT', f'/data/chia/{chia_network}/config/ssl/full_node/public_full_node.crt')

    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)


if __name__ == '__main__':
    main()

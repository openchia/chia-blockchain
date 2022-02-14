from typing import Any, Dict, List

import aiohttp
import asyncio
import logging
import os
import socket

IPS = [
    '188.114.97.3',
    '188.114.96.3',
    '104.21.34.211',
    '172.67.165.146',
]

WORKING_IP = IPS[0]

CLOUDFLARE_ENABLED = os.environ.get('CLOUDFLARE_TEST') == '1'

logger = logging.getLogger('farmer.cloudflare')


async def _cloudflare_test():

    for ip in IPS:
        try:
            for i in range(5):
                conn = aiohttp.TCPConnector(
                    use_dns_cache=False,
                    resolver=CloudFlareResolver(static_ip=ip),
                )
                async with aiohttp.ClientSession(connector=conn) as session:
                    async with session.get('https://pool-china.openchia.io/pool_info', verify_ssl=False) as r:
                        if not r.ok:
                            raise ValueError('not ok')
            else:
                return ip
        except Exception as e:
            logger.error("Failed to test cloudflare to %s: %s", ip, e)


async def cloudflare_testing():
    global WORKING_IP

    if os.environ.get('CLOUDFLARE_TEST') != '1':
        return

    while True:
        try:
            ip = await _cloudflare_test()
            logger.info('Cloudflare test result: %s', ip)
            if ip:
                WORKING_IP = ip
        except Exception:
            logger.error('Failed to run cloudflare test', exc_info=True)

        await asyncio.sleep(60)


class CloudFlareResolver(aiohttp.resolver.AbstractResolver):

    def __init__(self, *args, static_ip=None, **kwargs):
        self.static_ip = static_ip
        super().__init__(*args, **kwargs)

    async def resolve(
        self, hostname: str, port: int = 0, family: int = socket.AF_INET
    ) -> List[Dict[str, Any]]:
        return [{
            "hostname": hostname,
            "host": self.static_ip or WORKING_IP,
            "port": port,
            "family": socket.AF_INET,
            "proto": socket.IPPROTO_TCP,
            "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
        }]

    async def close(self):
        pass


if CLOUDFLARE_ENABLED:
    TCP_CONNECTOR = aiohttp.TCPConnector(use_dns_cache=False, resolver=CloudFlareResolver())
else:
    TCP_CONNECTOR = None

"""Explicit transport selection. Never fall back between credential audiences."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import ipaddress, re, ssl

@dataclass(frozen=True)
class Profile:
    mode: str
    url: str
    credentials_path: Path
    fingerprint: bytes | None = None

    def tls(self):
        if self.fingerprint is None:
            return ssl.create_default_context()
        from aiohttp import Fingerprint
        return Fingerprint(self.fingerprint)

def profile(options, data_dir='/data'):
    mode = options.get('transport', 'cloud')
    root = Path(data_dir)
    if mode == 'cloud':
        url = options.get('relay_url', '')
        u = urlsplit(url)
        if u.scheme != 'wss' or not u.hostname or u.username or u.password or u.fragment:
            raise ValueError('cloud_url_invalid')
        return Profile(mode, url, root / 'link.json')
    if mode != 'local':
        raise ValueError('transport_invalid')
    u = urlsplit(options.get('local_core_url', ''))
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('', '/'):
        raise ValueError('local_core_url_invalid')
    try:
        ip = ipaddress.ip_address(u.hostname)
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', u.hostname):
            raise ValueError('local_core_address_invalid') from None
        # DNS resolution and LAN validation must occur before opening a socket.
    else:
        if not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
            raise ValueError('local_core_address_invalid')
    try:
        port = u.port
    except ValueError:
        raise ValueError('local_core_url_invalid') from None
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('local_core_url_invalid')
    pin = options.get('local_core_sha256', '').replace(':', '').lower()
    if not re.fullmatch('[a-f0-9]{64}', pin):
        raise ValueError('local_core_pin_required')
    return Profile(mode, urlunsplit(('wss', u.netloc, '/dd-connector/local', '', '')), root / 'local-link.json', bytes.fromhex(pin))

class LANResolver:
    """Resolve once through aiohttp's resolver and return only eligible LAN IPs."""
    def __init__(self):
        from aiohttp.resolver import DefaultResolver
        self.delegate=DefaultResolver()
    async def resolve(self,host,port=0,family=0):
        rows=await self.delegate.resolve(host,port,family)
        if not rows:raise OSError('local_core_dns_empty')
        for row in rows:
            ip=ipaddress.ip_address(row['host'])
            if not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
                raise OSError('local_core_not_on_lan')
        return rows
    async def close(self):await self.delegate.close()

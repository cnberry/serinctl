"""Locate only a pinned controller; network scans require an explicit local range."""

import ipaddress
from concurrent.futures import ThreadPoolExecutor

from .client import IdentityMismatch, read_info, read_status
from .config import controller_url


def candidates(device):
    return list(dict.fromkeys(h for h in (device.hostname, device.host) if h))


def inspect_device(device, timeout=5):
    for host in candidates(device):
        try:
            return read_status(controller_url(host), timeout, expected_mac=device.mac)
        except IdentityMismatch:
            raise
        except ValueError:
            continue
    raise ValueError(
        "controller unavailable at configured addresses; use discover with a local network"
    )


def discover(device, timeout=2, network=None):
    if device.mac is None:
        raise ValueError("discovery requires a configured hardware MAC")
    hosts = candidates(device)
    if network is not None:
        try:
            net = ipaddress.IPv4Network(network, strict=True)
        except ValueError:
            raise ValueError("network must be an IPv4 CIDR") from None
        local = (
            ipaddress.IPv4Network("10.0.0.0/8"),
            ipaddress.IPv4Network("172.16.0.0/12"),
            ipaddress.IPv4Network("192.168.0.0/16"),
        )
        if net.num_addresses > 256 or not any(net.subnet_of(block) for block in local):
            raise ValueError("scan requires a private IPv4 network of /24 or smaller")
        hosts.extend(str(ip) for ip in net.hosts())
    hosts = list(dict.fromkeys(hosts))

    def probe(host):
        try:
            info = read_info(controller_url(host), timeout, expected_mac=device.mac)
            return {"endpoint": host, "device": device.identity(), "hardware": info}
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        found = [result for result in executor.map(probe, hosts) if result is not None]
    if not found:
        raise ValueError("no matching controller found; configuration unchanged")
    # A hostname and IP may name the same endpoint. Never auto-save or choose
    # between distinct advertised IPs sharing an identity.
    unique = {r["hardware"]["ip"]: r for r in found}
    if len(unique) != 1:
        raise ValueError("multiple endpoints claim the hardware identity; configuration unchanged")
    return next(iter(unique.values()))

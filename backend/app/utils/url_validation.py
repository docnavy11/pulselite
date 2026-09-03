"""URL validation utilities to prevent SSRF attacks.

Validates that URLs use http/https and do not resolve to private/reserved IP ranges.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private and reserved networks that must be blocked
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address falls within a blocked private/reserved range."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # If we can't parse it, reject it
    return any(addr in network for network in _BLOCKED_NETWORKS)


def validate_url_not_private(url: str) -> None:
    """Validate that a URL uses http/https and does not resolve to a private IP.

    Raises ValueError if the URL is invalid, uses a non-http(s) scheme,
    or resolves to a private/reserved IP address.
    """
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid hostname")

    # Resolve hostname and check all returned IPs
    try:
        addrinfo = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname {hostname!r}: {exc}") from exc

    if not addrinfo:
        raise ValueError(f"No addresses found for hostname {hostname!r}")

    for family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            raise ValueError(
                f"URL resolves to a private/reserved IP address ({ip_str}); "
                f"request blocked to prevent SSRF"
            )


async def async_validate_url_not_private(url: str) -> None:
    """Async version of validate_url_not_private.

    Runs DNS resolution in a thread to avoid blocking the event loop.
    """
    import asyncio

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, validate_url_not_private, url)

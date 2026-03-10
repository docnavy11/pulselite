import ipaddress

import httpx

PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_loopback or addr.is_private or any(addr in net for net in PRIVATE_RANGES)
    except ValueError:
        return True


async def get_country(ip: str) -> tuple[str | None, str | None]:
    """Returns (country_code, country_name) or (None, None) for private/unknown IPs."""
    if not ip or is_private_ip(ip):
        return None, None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("countryCode"), data.get("country")
    except Exception:
        pass
    return None, None

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .storage import atomic_write_json


USER_AGENT = "KaohsiungHomeFinder/1.0 (local personal home search)"


def _get_json(url: str, *, timeout: int = 20) -> dict[str, Any] | list[Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"geocodes": {}, "routes": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"geocodes": {}, "routes": {}}
    return payload if isinstance(payload, dict) else {"geocodes": {}, "routes": {}}


def estimate_commute(
    origin: str,
    destinations: list[dict[str, str]],
    *,
    cache_path: Path,
    get_json=_get_json,
    sleep=time.sleep,
) -> dict[str, Any]:
    cache = _load_cache(cache_path)
    geocodes = cache.setdefault("geocodes", {})
    routes = cache.setdefault("routes", {})
    addresses = [origin, *[item["address"] for item in destinations]]
    coordinates: list[dict[str, float]] = []
    for address in addresses:
        cached = geocodes.get(address)
        if not cached:
            query = urllib.parse.urlencode({"q": address, "format": "jsonv2", "limit": 1, "countrycodes": "tw"})
            result = get_json(f"https://nominatim.openstreetmap.org/search?{query}")
            if not isinstance(result, list) or not result:
                raise ValueError(f"無法定位：{address}")
            cached = {"lat": float(result[0]["lat"]), "lon": float(result[0]["lon"])}
            geocodes[address] = cached
            atomic_write_json(cache_path, cache)
            sleep(1.05)
        coordinates.append(cached)

    route_key = "|".join(addresses)
    cached_route = routes.get(route_key)
    was_cached = cached_route is not None
    if not cached_route:
        coordinate_text = ";".join(f"{item['lon']},{item['lat']}" for item in coordinates)
        destination_indexes = ";".join(str(index) for index in range(1, len(coordinates)))
        url = f"https://router.project-osrm.org/table/v1/driving/{coordinate_text}?sources=0&destinations={destination_indexes}&annotations=duration,distance"
        payload = get_json(url)
        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            raise ValueError("路線服務目前無法估算")
        durations = (payload.get("durations") or [[]])[0]
        distances = (payload.get("distances") or [[]])[0]
        cached_route = [{
            "name": destination["name"],
            "address": destination["address"],
            "minutes": round(float(durations[index]) / 60),
            "distance_km": round(float(distances[index]) / 1000, 1),
        } for index, destination in enumerate(destinations)]
        routes[route_key] = cached_route
        atomic_write_json(cache_path, cache)
    return {"origin": origin, "estimates": cached_route, "cached": was_cached}

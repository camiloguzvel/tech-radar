"""Asignación de instituciones a hubs por radio haversine."""

from __future__ import annotations

import math

from radar.domains.loader import Hub

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def assign_hub(
    lat: float | None, lon: float | None, country: str | None, hubs: list[Hub]
) -> tuple[str, str] | None:
    """Devuelve (hub_id, hub_method) o None.

    El país debe estar en `hub.countries` (separa Shenzhen de Hong Kong). Si varios
    centros cubren el punto, gana el más cercano. Sin coordenadas, solo aplican los
    hubs de país completo.
    """
    if country is None:
        return None
    best: tuple[float, str] | None = None
    for hub in hubs:
        if country not in hub.countries:
            continue
        if hub.whole_country:
            return hub.id, "country"
        if lat is None or lon is None:
            continue
        for center in hub.centers:
            distance = haversine_km(lat, lon, center.lat, center.lon)
            if distance <= center.radius_km and (best is None or distance < best[0]):
                best = (distance, hub.id)
    return (best[1], "radius") if best else None

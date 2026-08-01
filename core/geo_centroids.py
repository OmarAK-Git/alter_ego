"""Static label -> lat/long centroid lookup for geo-velocity (H13).

No live geocoding dependency; covers only the label vocabulary in active use
by batch/synthetic/generator.py today. Extend this table as new labels appear
in production event data, do not fall back to an external API.
"""
import math

GEO_CENTROIDS: dict[str, tuple[float, float]] = {
    "US-East": (39.0438, -77.4874),
    "US-West": (37.3382, -121.8863),
    "EU-Central": (50.1109, 8.6821),
    "AP-South": (19.0760, 72.8777),
    "US-East-DC1": (39.0438, -77.4874),
    "RU-Moscow": (55.7558, 37.6173),
}


def lookup_centroid(label: str) -> tuple[float, float] | None:
    return GEO_CENTROIDS.get(label)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))

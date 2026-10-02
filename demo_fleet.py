"""In-memory moving fleet used when the project runs in public demo mode."""

from __future__ import annotations

import math
import random
import threading
import time


INDIA_CITIES = (
    ("delhi", (28.6139, 77.2090)),
    ("srinagar", (34.0837, 74.7973)),
    ("chandigarh", (30.7333, 76.7794)),
    ("jaipur", (26.9124, 75.7873)),
    ("lucknow", (26.8467, 80.9462)),
    ("patna", (25.5941, 85.1376)),
    ("guwahati", (26.1445, 91.7362)),
    ("kolkata", (22.5726, 88.3639)),
    ("bhubaneswar", (20.2961, 85.8245)),
    ("ahmedabad", (23.0225, 72.5714)),
    ("mumbai", (19.0760, 72.8777)),
    ("pune", (18.5204, 73.8567)),
    ("bhopal", (23.2599, 77.4126)),
    ("hyderabad", (17.3850, 78.4867)),
    ("bengaluru", (12.9716, 77.5946)),
    ("chennai", (13.0827, 80.2707)),
    ("kochi", (9.9312, 76.2673)),
    ("goa", (15.2993, 74.1240)),
    ("ranchi", (23.3441, 85.3096)),
    ("imphal", (24.8170, 93.9368)),
)


class DemoFleet:
    """Generates deterministic, realistic-looking driver movement around city centers."""

    def __init__(
        self,
        center: tuple[float, float],
        driver_count: int,
        nationwide: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._random = random.Random(20260923)
        self._last_update = time.monotonic()
        locations = INDIA_CITIES if nationwide else (("local", center),)
        self._drivers = []
        for index in range(1, driver_count + 1):
            city, city_center = locations[(index - 1) % len(locations)]
            self._drivers.append({
                "driver_id": f"demo-{city}-{index:02d}",
                "center_lat": city_center[0],
                "center_lon": city_center[1],
                "lat": city_center[0] + self._random.uniform(-0.08, 0.08),
                "lon": city_center[1] + self._random.uniform(-0.08, 0.08),
                "heading": self._random.uniform(0, math.tau),
                "speed_kmh": round(self._random.uniform(18, 42), 1),
            })

    def _advance_locked(self) -> None:
        now = time.monotonic()
        elapsed_sec = min(now - self._last_update, 5.0)
        self._last_update = now

        for driver in self._drivers:
            driver["heading"] += self._random.uniform(-0.22, 0.22)
            driver["speed_kmh"] = round(
                min(48, max(12, driver["speed_kmh"] + self._random.uniform(-2.5, 2.5))),
                1,
            )
            distance_km = driver["speed_kmh"] * elapsed_sec / 3600
            lat_delta = distance_km * math.cos(driver["heading"]) / 111.32
            lon_delta = distance_km * math.sin(driver["heading"]) / (
                111.32 * math.cos(math.radians(driver["lat"]))
            )
            driver["lat"] += lat_delta
            driver["lon"] += lon_delta

            if (
                abs(driver["lat"] - driver["center_lat"]) > 0.12
                or abs(driver["lon"] - driver["center_lon"]) > 0.12
            ):
                driver["heading"] += math.pi

    @staticmethod
    def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_km = 6371.0088
        lat_delta = math.radians(lat2 - lat1)
        lon_delta = math.radians(lon2 - lon1)
        value = (
            math.sin(lat_delta / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(lon_delta / 2) ** 2
        )
        return 2 * earth_radius_km * math.asin(math.sqrt(value))

    @staticmethod
    def _public_driver(driver: dict) -> dict:
        return {
            "driver_id": driver["driver_id"],
            "lat": round(driver["lat"], 6),
            "lon": round(driver["lon"], 6),
            "is_alive": True,
            "speed_kmh": driver["speed_kmh"],
            "last_seen_sec_ago": 0.0,
        }

    def drivers(self) -> list[dict]:
        with self._lock:
            self._advance_locked()
            return [self._public_driver(driver) for driver in self._drivers]

    def nearby(self, lat: float, lon: float, radius_km: float, limit: int) -> list[dict]:
        with self._lock:
            self._advance_locked()
            nearby_drivers = []
            for driver in self._drivers:
                distance_km = self._distance_km(lat, lon, driver["lat"], driver["lon"])
                if distance_km <= radius_km:
                    public_driver = self._public_driver(driver)
                    public_driver["distance_km"] = round(distance_km, 3)
                    nearby_drivers.append(public_driver)

            nearby_drivers.sort(key=lambda driver: driver["distance_km"])
            return nearby_drivers[:limit]

"""In-memory moving fleet used when the project runs in public demo mode."""

from __future__ import annotations

import math
import random
import threading
import time


class DemoFleet:
    """Generates deterministic, realistic-looking driver movement around a centre point."""

    def __init__(self, center: tuple[float, float], driver_count: int) -> None:
        self._center = center
        self._lock = threading.Lock()
        self._random = random.Random(20260923)
        self._last_update = time.monotonic()
        self._drivers = [
            {
                "driver_id": f"demo-driver-{index:02d}",
                "lat": center[0] + self._random.uniform(-0.035, 0.035),
                "lon": center[1] + self._random.uniform(-0.035, 0.035),
                "heading": self._random.uniform(0, math.tau),
                "speed_kmh": round(self._random.uniform(18, 42), 1),
            }
            for index in range(1, driver_count + 1)
        ]

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

            # Keep the simulated fleet within the visible city area.
            if abs(driver["lat"] - self._center[0]) > 0.055 or abs(driver["lon"] - self._center[1]) > 0.055:
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

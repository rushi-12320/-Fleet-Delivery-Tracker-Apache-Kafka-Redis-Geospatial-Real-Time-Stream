import time
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from config import CENTER, DEMO_MODE, NUM_DRIVERS, PORT, get_redis_client
from demo_fleet import DemoFleet

app = FastAPI(title="Delivery Tracker API", version="2.0.0")

# Enable CORS for local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

demo_fleet = DemoFleet(CENTER, NUM_DRIVERS) if DEMO_MODE else None
r = None if DEMO_MODE else get_redis_client()


@app.get("/health")
def health():
    """Healthcheck endpoint for the active telemetry mode."""
    if DEMO_MODE:
        return {"status": "ok", "mode": "demo", "redis": False}

    try:
        ping = r.ping()  # type: ignore[union-attr]
        return {"status": "ok", "mode": "streaming", "redis": ping}
    except Exception as exc:
        return {"status": "error", "redis": False, "error": str(exc)}


@app.get("/stats")
def get_stats():
    """Returns overview statistics of driver counts and active heartbeats."""
    if DEMO_MODE:
        drivers = demo_fleet.drivers()  # type: ignore[union-attr]
        return {
            "total_registered": len(drivers),
            "active_now": len(drivers),
            "offline": 0,
            "redis_connected": False,
            "mode": "demo",
        }

    try:
        total_drivers = r.zcard("drivers:geo")  # type: ignore[union-attr]
        alive_keys = r.keys("driver:*:alive")  # type: ignore[union-attr]
        return {
            "total_registered": total_drivers,
            "active_now": len(alive_keys),
            "offline": max(0, total_drivers - len(alive_keys)),
            "redis_connected": True,
        }
    except Exception as exc:
        return {
            "total_registered": 0,
            "active_now": 0,
            "offline": 0,
            "redis_connected": False,
            "error": str(exc),
        }


@app.get("/drivers")
def list_all_drivers():
    """List all registered drivers in Redis with their live coordinates and alive status."""
    if DEMO_MODE:
        drivers = demo_fleet.drivers()  # type: ignore[union-attr]
        return {"count": len(drivers), "drivers": drivers, "mode": "demo"}

    members = r.zrange("drivers:geo", 0, -1)  # type: ignore[union-attr]
    if not members:
        return {"count": 0, "drivers": []}

    coords = r.geopos("drivers:geo", *members)  # type: ignore[union-attr]

    # Check alive status and info in one pipeline
    pipe = r.pipeline()  # type: ignore[union-attr]
    for name in members:
        pipe.exists(f"driver:{name}:alive")
        pipe.hgetall(f"driver:{name}:info")
    results = pipe.execute()

    drivers = []
    now = time.time()
    for i, name in enumerate(members):
        coord = coords[i]
        if not coord:
            continue
        alive = bool(results[i * 2])
        info = results[i * 2 + 1] or {}
        speed = float(info.get("speed_kmh", 0.0))
        last_ts = float(info.get("ts", now))
        age_sec = round(now - last_ts, 1)

        drivers.append({
            "driver_id": name,
            "lat": round(coord[1], 6),
            "lon": round(coord[0], 6),
            "is_alive": alive,
            "speed_kmh": speed,
            "last_seen_sec_ago": age_sec,
        })

    # Sort so active drivers appear first
    drivers.sort(key=lambda d: (not d["is_alive"], d["driver_id"]))
    return {"count": len(drivers), "drivers": drivers}


@app.get("/drivers/nearby")
def nearby_drivers(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=50),
    limit: int = Query(5, ge=1, le=50),
):
    """
    Find live nearby drivers within a radius (km).
    Stale drivers whose heartbeat expired in Redis (>15s) are automatically filtered out.
    """
    if DEMO_MODE:
        drivers = demo_fleet.nearby(lat, lon, radius_km, limit)  # type: ignore[union-attr]
        return {"count": len(drivers), "drivers": drivers, "mode": "demo"}

    # 1. Ask Redis for the closest drivers. Fetch extra candidates because stale ones get filtered.
    results = r.geosearch(  # type: ignore[union-attr]
        "drivers:geo",
        longitude=lon,
        latitude=lat,
        radius=radius_km,
        unit="km",
        sort="ASC",
        count=limit * 4,
        withdist=True,
        withcoord=True,
    )
    if not results:
        return {"count": 0, "drivers": []}

    # 2. Check every candidate's heartbeat key in ONE pipeline round-trip
    pipe = r.pipeline()  # type: ignore[union-attr]
    for name, _dist, _coord in results:
        pipe.exists(f"driver:{name}:alive")
        pipe.hget(f"driver:{name}:info", "speed_kmh")
    exec_res = pipe.execute()

    alive_flags = [exec_res[i * 2] for i in range(len(results))]
    speeds = [exec_res[i * 2 + 1] for i in range(len(results))]

    # 3. Keep only drivers that are still alive, up to `limit`
    drivers = []
    for (name, dist, (dlon, dlat)), alive, speed in zip(results, alive_flags, speeds):
        if not alive:
            continue
        drivers.append({
            "driver_id": name,
            "distance_km": round(dist, 3),
            "lat": round(dlat, 6),
            "lon": round(dlon, 6),
            "speed_kmh": float(speed) if speed else 0.0,
            "is_alive": True,
        })
        if len(drivers) == limit:
            break

    return {"count": len(drivers), "drivers": drivers}


@app.get("/", response_class=HTMLResponse)
def index():
    """Interactive Real-Time Fleet Tracking Dashboard with Leaflet.js"""
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Real-Time Delivery Fleet Tracker | Kafka & Redis</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <style>
    :root {
      --bg: #0b0f19;
      --surface: #131b2e;
      --surface-border: #1e2c4a;
      --primary: #38bdf8;
      --accent: #6366f1;
      --online: #10b981;
      --offline: #ef4444;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    /* Header */
    header {
      background: rgba(19, 27, 46, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--surface-border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 1000;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .logo-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #38bdf8, #6366f1);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      font-weight: 700;
      color: white;
      box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
    .brand h1 {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .brand span {
      font-size: 0.75rem;
      color: var(--text-muted);
      display: block;
    }
    .metrics {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .metric-card {
      background: rgba(11, 15, 25, 0.6);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 6px 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .metric-label { font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-val { font-size: 1.1rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .metric-val.active { color: var(--online); }
    .metric-val.offline { color: var(--offline); }

    /* Main layout */
    .main-container {
      display: flex;
      flex: 1;
      position: relative;
      overflow: hidden;
    }
    #map {
      flex: 1;
      height: 100%;
      background: #090d16;
    }
    .sidebar {
      width: 380px;
      background: var(--surface);
      border-left: 1px solid var(--surface-border);
      display: flex;
      flex-direction: column;
      height: 100%;
      z-index: 500;
    }
    .sidebar-header {
      padding: 16px;
      border-bottom: 1px solid var(--surface-border);
    }
    .sidebar-header h2 {
      font-size: 0.95rem;
      font-weight: 600;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .refresh-badge {
      font-size: 0.7rem;
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      padding: 3px 8px;
      border-radius: 12px;
      border: 1px solid rgba(56, 189, 248, 0.3);
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .pulse-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--online);
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 0.7; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(0.9); opacity: 0.7; }
    }
    .search-box {
      background: var(--bg);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 10px;
      margin-top: 8px;
      font-size: 0.8rem;
    }
    .search-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .driver-list {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .driver-card {
      background: rgba(11, 15, 25, 0.5);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 10px 14px;
      transition: all 0.2s ease;
      cursor: pointer;
    }
    .driver-card:hover {
      border-color: var(--primary);
      transform: translateX(2px);
      background: rgba(56, 189, 248, 0.05);
    }
    .driver-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }
    .driver-name {
      font-weight: 600;
      font-size: 0.88rem;
    }
    .status-pill {
      font-size: 0.68rem;
      padding: 2px 7px;
      border-radius: 10px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .status-pill.online {
      background: rgba(16, 185, 129, 0.15);
      color: var(--online);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-pill.offline {
      background: rgba(239, 68, 68, 0.15);
      color: var(--offline);
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .driver-details {
      display: flex;
      justify-content: space-between;
      font-size: 0.75rem;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
    }
    /* Custom Map Markers */
    .custom-driver-marker {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .marker-dot {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--online);
      border: 2px solid white;
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.8);
      transition: transform 0.3s ease;
    }
    .marker-dot.offline {
      background: var(--offline);
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
    }
    .marker-label {
      background: rgba(11, 15, 25, 0.85);
      color: white;
      font-size: 10px;
      padding: 1px 4px;
      border-radius: 4px;
      margin-left: 6px;
      white-space: nowrap;
      border: 1px solid var(--surface-border);
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo-icon">🚚</div>
      <div>
        <h1>Fleet Delivery Tracker</h1>
        <span>Apache Kafka & Redis Geospatial Real-Time Stream</span>
      </div>
    </div>
    <div class="metrics">
      <div class="metric-card">
        <span class="metric-label">Active Drivers</span>
        <span class="metric-val active" id="stat-active">0</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Offline</span>
        <span class="metric-val offline" id="stat-offline">0</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Total Registered</span>
        <span class="metric-val" id="stat-total">0</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Heartbeat TTL</span>
        <span class="metric-val" style="color: var(--primary);">15s</span>
      </div>
    </div>
  </header>

  <div class="main-container">
    <div id="map"></div>
    <div class="sidebar">
      <div class="sidebar-header">
        <h2>
          <span>Live Fleet Status</span>
          <span class="refresh-badge"><span class="pulse-dot"></span> Live Polling (2s)</span>
        </h2>
        <div class="search-box">
          <div class="search-row">
            <span>Radius Search Filter:</span>
            <span id="radius-val" style="color: var(--primary); font-weight:600;">10 km</span>
          </div>
          <input type="range" id="radius-slider" min="1" max="25" value="10" style="width: 100%; accent-color: var(--primary);">
          <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">
            Click anywhere on map to set a radar search center.
          </div>
        </div>
      </div>
      <div class="driver-list" id="driver-list">
        <div style="padding: 20px; text-align: center; color: var(--text-muted);">
          Connecting to API and fetching driver telemetry...
        </div>
      </div>
    </div>
  </div>

  <script>
    const CENTER = [19.0760, 72.8777]; // Mumbai
    const map = L.map('map', { zoomControl: false }).setView(CENTER, 12);
    L.control.zoom({ position: 'topright' }).addTo(map);

    // Dark sleek CartoDB tile layer
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=cb1_3s4n_1_d89c8e248b7f689e21a13693', {
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  subdomains: 'abcd',
  maxZoom: 19
}).addTo(map);

    // Search circle
    let searchCenter = CENTER;
    let searchRadiusKm = 10;
    const radarCircle = L.circle(searchCenter, {
      radius: searchRadiusKm * 1000,
      color: '#38bdf8',
      fillColor: '#38bdf8',
      fillOpacity: 0.08,
      weight: 1.5,
      dashArray: '5, 5'
    }).addTo(map);

    const centerMarker = L.circleMarker(searchCenter, {
      radius: 6,
      color: '#ffffff',
      fillColor: '#38bdf8',
      fillOpacity: 1,
      weight: 2
    }).addTo(map).bindPopup("<b>Radar Center</b><br>Click anywhere on map to reposition search center.");

    map.on('click', (e) => {
      searchCenter = [e.latlng.lat, e.latlng.lng];
      radarCircle.setLatLng(searchCenter);
      centerMarker.setLatLng(searchCenter);
      fetchNearbyDrivers();
    });

    document.getElementById('radius-slider').addEventListener('input', (e) => {
      searchRadiusKm = parseFloat(e.target.value);
      document.getElementById('radius-val').innerText = `${searchRadiusKm} km`;
      radarCircle.setRadius(searchRadiusKm * 1000);
      fetchNearbyDrivers();
    });

    const driverMarkers = {};

    function createDriverIcon(driverId, isAlive) {
      return L.divIcon({
        className: 'custom-driver-marker',
        html: `
          <div style="display:flex;align-items:center;">
            <div class="marker-dot ${isAlive ? '' : 'offline'}"></div>
            <div class="marker-label">${driverId}</div>
          </div>
        `,
        iconSize: [80, 24],
        iconAnchor: [9, 12]
      });
    }

    async function fetchFleet() {
      const listContainer = document.getElementById('driver-list');

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const res = await fetch('/drivers', { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();
        const drivers = data.drivers || [];

        let activeCount = 0;
        let offlineCount = 0;
        listContainer.innerHTML = '';

        if (drivers.length === 0) {
          listContainer.innerHTML = `
            <div style="padding: 20px; text-align: center; color: var(--text-muted); line-height: 1.6;">
              No live telemetry yet.<br>
              Start the producer or connect Redis/Kafka and the map will populate automatically.
            </div>
          `;
          document.getElementById('stat-active').innerText = '0';
          document.getElementById('stat-offline').innerText = '0';
          document.getElementById('stat-total').innerText = '0';
          return;
        }

        drivers.forEach(d => {
          if (d.is_alive) activeCount++;
          else offlineCount++;

          // Update or add map marker
          const pos = [d.lat, d.lon];
          if (driverMarkers[d.driver_id]) {
            driverMarkers[d.driver_id].setLatLng(pos);
            driverMarkers[d.driver_id].setIcon(createDriverIcon(d.driver_id, d.is_alive));
            driverMarkers[d.driver_id].getPopup().setContent(`
              <b>${d.driver_id}</b><br>
              Status: <span style="color:${d.is_alive ? '#10b981':'#ef4444'};font-weight:600;">${d.is_alive ? 'ONLINE' : 'OFFLINE'}</span><br>
              Speed: ${d.speed_kmh} km/h<br>
              Lat: ${d.lat}, Lon: ${d.lon}<br>
              Last seen: ${d.last_seen_sec_ago}s ago
            `);
          } else {
            const marker = L.marker(pos, { icon: createDriverIcon(d.driver_id, d.is_alive) })
              .addTo(map)
              .bindPopup(`
                <b>${d.driver_id}</b><br>
                Status: <span style="color:${d.is_alive ? '#10b981':'#ef4444'};font-weight:600;">${d.is_alive ? 'ONLINE' : 'OFFLINE'}</span><br>
                Speed: ${d.speed_kmh} km/h<br>
                Lat: ${d.lat}, Lon: ${d.lon}<br>
                Last seen: ${d.last_seen_sec_ago}s ago
              `);
            driverMarkers[d.driver_id] = marker;
          }

          // Build sidebar card
          const card = document.createElement('div');
          card.className = 'driver-card';
          card.innerHTML = `
            <div class="driver-card-header">
              <span class="driver-name">${d.driver_id}</span>
              <span class="status-pill ${d.is_alive ? 'online' : 'offline'}">${d.is_alive ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <div class="driver-details">
              <span>Speed: ${d.speed_kmh} km/h</span>
              <span>${d.is_alive ? 'Active' : d.last_seen_sec_ago + 's ago'}</span>
            </div>
          `;
          card.onclick = () => {
            map.panTo([d.lat, d.lon]);
            if (driverMarkers[d.driver_id]) {
              driverMarkers[d.driver_id].openPopup();
            }
          };
          listContainer.appendChild(card);
        });

        document.getElementById('stat-active').innerText = activeCount;
        document.getElementById('stat-offline').innerText = offlineCount;
        document.getElementById('stat-total').innerText = drivers.length;

      } catch (err) {
        console.error("Failed to fetch drivers:", err);
        listContainer.innerHTML = `
          <div style="padding: 20px; text-align: center; color: #fca5a5; line-height: 1.6;">
            Telemetry request timed out or backend is unavailable.<br>
            Check Redis and Kafka connectivity, then refresh the page.
          </div>
        `;
        document.getElementById('stat-active').innerText = '0';
        document.getElementById('stat-offline').innerText = '0';
        document.getElementById('stat-total').innerText = '0';
      }
    }

    async function fetchNearbyDrivers() {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const url = `/drivers/nearby?lat=${searchCenter[0]}&lon=${searchCenter[1]}&radius_km=${searchRadiusKm}&limit=20`;
        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await res.json();
        console.log(`Nearby drivers (${data.count}):`, data.drivers);
      } catch (err) {
        console.error("Nearby search error:", err);
      }
    }

    // Initial fetch & loop every 2 seconds
    fetchFleet();
    setInterval(fetchFleet, 2000);
  </script>
</body>
</html>
""")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=PORT, reload=True)

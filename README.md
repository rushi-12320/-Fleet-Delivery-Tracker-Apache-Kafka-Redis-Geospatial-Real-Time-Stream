# Fleet Delivery Tracker

A real-time delivery fleet monitoring system built with Apache Kafka, Redis geospatial indexing, and FastAPI. It simulates live GPS telemetry from drivers, streams events through Kafka, stores live positions in Redis, and exposes a map-based dashboard and REST API for tracking vehicles in near real time.

## Live Demo

The application is published and available here:

https://delivery-tracking-system.onrender.com

## Deployment Platform

This project is configured for a managed Redis deployment on Upstash and a public Render web service for the dashboard. The live Redis instance is available here:

https://console.upstash.com/redis/fb39a1ba-9192-4f0c-9c3e-b70f4f151f3a

## Overview

This application is designed for scenarios where fleets need to monitor delivery vehicles, check nearby drivers, and expose operational insights through a simple dashboard. It demonstrates how to combine streaming data, geospatial queries, and a lightweight web API in a production-style architecture.

## Features

- Real-time GPS simulation for multiple drivers
- Kafka-based event ingestion pipeline
- Redis geospatial indexing for fast location queries
- Heartbeat tracking for active vs stale drivers
- FastAPI REST API for health checks and nearby-driver queries
- Live dashboard with map rendering and fleet metrics
- Local Docker-based setup for Kafka and Redis
- Cloud-friendly configuration for services such as Upstash

## Architecture

```text
GPS Producer (Python) --> Kafka Topic --> Kafka Consumer (Python) --> Redis GeoIndex + Metadata
                                                        |
                                                        +--> FastAPI API / Dashboard
```

## Tech Stack

- Python 3.10+
- FastAPI
- Apache Kafka
- Redis
- Docker Compose
- Confluent Kafka Python client

## Project Structure

```text
.
├── api.py                  # FastAPI dashboard and API routes
├── config.py               # Environment-driven configuration
├── consumer.py             # Kafka consumer writing to Redis
├── producer.py             # Simulated GPS generator
├── run_all.py              # Starts producer, consumer, and API together
├── docker-compose.yml      # Kafka + Redis local stack
├── Dockerfile              # Container build for deployment
├── requirements.txt        # Python dependencies
├── .env.example            # Sample environment configuration
├── DEPLOYMENT.md           # Cloud deployment instructions
├── render.yaml             # Render deployment configuration
├── .gitignore              # Ignore rules for Python projects
├── LICENSE                 # MIT license
├── README.md               # Main project documentation
└── venv/                   # Local virtual environment (ignored in Git)
```

## Prerequisites

Before running the app locally, make sure you have:

- Python 3.10 or newer
- Docker and Docker Compose
- A terminal or IDE with access to the project folder

## Quick Start

### 1) Create and activate a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Start local infrastructure

This project includes a local Kafka and Redis setup using Docker.

```bash
docker compose up -d
```

### 4) Configure environment variables

Copy the sample file and adjust values if needed:

```bash
copy .env.example .env
```

Then review the values inside `.env`.

### 5) Run the application

To start all services together:

```bash
python run_all.py
```

This starts:

- the Kafka producer simulating delivery vehicle positions
- the Kafka consumer that writes to Redis
- the FastAPI dashboard and REST API

Open the dashboard in your browser:

```text
http://localhost:8000
```

The health endpoint is available at:

```text
http://localhost:8000/health
```

## API Endpoints

### Health

```http
GET /health
```

Returns Redis connectivity and service health status.

### Fleet statistics

```http
GET /stats
```

Returns counts of total drivers, active drivers, and offline drivers.

### All registered drivers

```http
GET /drivers
```

Returns current geolocation and metadata for all tracked drivers.

### Nearby drivers

```http
GET /drivers/nearby?lat=19.076&lon=72.877&radius_km=5&limit=10
```

Returns drivers within a defined radius from the provided latitude and longitude.

## Environment Variables

The project uses environment variables defined in `.env.example` and `config.py`.

Key settings include:

- `PORT`
- `REDIS_URL` or `REDIS_HOST` / `REDIS_PORT`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_SECURITY_PROTOCOL`
- `KAFKA_SASL_USERNAME`
- `KAFKA_SASL_PASSWORD`
- `KAFKA_TOPIC`
- `NUM_DRIVERS`

## Deployment

For cloud deployment guidance, see [DEPLOYMENT.md](DEPLOYMENT.md).

This project is also configured for Render deployment via [render.yaml](render.yaml).

## Security Notes

- Never commit real secrets, access keys, or production credentials.
- Keep `.env` local and excluded from version control.
- Use secure Kafka and Redis credentials when deploying to managed cloud services.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request with a clear description of the change.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

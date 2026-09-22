# 🚀 Cloud Deployment Guide

This guide explains how to deploy the **Fleet Delivery Tracker** to a managed cloud stack using **Upstash Redis** and optional Kafka services. The project is designed to work with a live Upstash Redis instance, including the deployed platform available here:

https://console.upstash.com/redis/fb39a1ba-9192-4f0c-9c3e-b70f4f151f3a

The setup below is suitable for free or low-cost managed deployments and can be used without needing to host Redis locally.

```
┌────────────────────────────────────────────────────────┐
│             Render (100% Free Web Service)             │
│  - FastAPI Web Dashboard + REST API (api.py)           │
│  - Kafka Background Consumer (consumer.py)             │
│  - GPS Telemetry Simulator (producer.py)               │
└──────────────┬──────────────────────────┬──────────────┘
               │ SASL_SSL                 │ SSL (rediss://)
               ▼                          ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Upstash Kafka (Serverless)   │ │ Upstash Redis (Serverless)   │
│ - Free Tier: 10,000 msgs/day │ │ - Free Tier: 10,000 req/day  │
│ - No credit card required    │ │ - No credit card required    │
│ - Fully managed Kafka topic  │ │ - Geospatial & Heartbeats    │
└──────────────────────────────┘ └──────────────────────────────┘
```

---

## Step 1: Create or Connect Your Upstash Services

Upstash offers serverless Kafka and Redis infrastructure for low-latency real-time workloads. This project is already aligned to the managed Redis platform shown above, and you can use the same pattern for Kafka and Redis connections in your environment.

### 1.1 Create Free Kafka Topic
1. Go to [console.upstash.com](https://console.upstash.com/) and sign up with GitHub or Google.
2. In the top navigation, click **Kafka**.
3. Click **Create Cluster**:
   - Name: `delivery-kafka`
   - Region: Select any region close to you
   - Type: **Serverless** (Free)
4. Inside the cluster, click **Topics** -> **Create Topic**:
   - Name: `driver-locations`
   - Partitions: `1` (or `3`)
   - Retention: 1 day
5. Click **Connect to Cluster** -> select **Python**:
   - Copy **Bootstrap Servers** (e.g., `clean-camel-12345-us1-kafka.upstash.io:9092`)
   - Copy **Username**
   - Copy **Password**

### 1.2 Create Free Redis Database
1. In the top navigation, click **Redis**.
2. Click **Create Database**:
   - Name: `delivery-redis`
   - Type: **Serverless** (Free)
3. Scroll down to **Connect Details** -> click the **rediss:// (ioredis/Python)** tab.
4. Copy the complete URL:
   `rediss://default:YOUR_PASSWORD@your-cluster.upstash.io:6379`

---

## Step 2: Push Project to GitHub

Open a terminal in your project directory:

```bash
git init
git add .
git commit -m "Deploy Delivery Tracking System"
git branch -M main
```

Create a new repository on [GitHub](https://github.com/new) and push your code:

```bash
git remote add origin https://github.com/<YOUR_USERNAME>/delivery-tracking-system.git
git push -u origin main
```

---

## Step 3: 1-Click Deploy to Render (100% Free)

Render provides free container hosting with public HTTPS URLs:

1. Sign up or log into [dashboard.render.com](https://dashboard.render.com/).
2. Click **New +** (top right) -> select **Blueprint**.
3. Connect your GitHub account and select your `delivery-tracking-system` repository.
4. Render will read [`render.yaml`](file:///c:/Users/rp520/Documents/Delivery%20Tracking%20System/render.yaml) automatically.
5. In the configuration screen, fill in the 4 environment variables from Step 1:
   - `REDIS_URL`: `rediss://default:...@...upstash.io:6379`
   - `KAFKA_BOOTSTRAP_SERVERS`: `...upstash.io:9092`
   - `KAFKA_SASL_USERNAME`: `...`
   - `KAFKA_SASL_PASSWORD`: `...`
6. Click **Apply**.

Render will automatically build your Docker container, start the background consumer, the simulated GPS producer, and host the live FastAPI dashboard with a free `https://delivery-tracking-system.onrender.com` URL!

---

## Alternative: Deploy to Koyeb or Railway

You can also deploy this exact container directly to:
- **Koyeb** (Free 512MB Nano service): Click "Create Service" -> select GitHub repo -> select "Dockerfile" -> enter environment variables.
- **Fly.io**: Run `fly launch` in this folder, set secrets with `fly secrets set REDIS_URL=...`, and deploy!

---

## Testing Cloud Deployment Locally Before Deploying

You can test your cloud credentials locally at any time by creating a `.env` file:

```env
REDIS_URL=rediss://default:YOUR_PASSWORD@your-db.upstash.io:6379
KAFKA_BOOTSTRAP_SERVERS=your-kafka.upstash.io:9092
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=SCRAM-SHA-256
KAFKA_SASL_USERNAME=your_username
KAFKA_SASL_PASSWORD=your_password
```

Then simply run:
```bash
python run_all.py
```
And watch the local app connect directly to cloud Kafka & Redis!

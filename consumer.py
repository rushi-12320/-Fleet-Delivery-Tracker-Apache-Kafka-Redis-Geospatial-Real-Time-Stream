import datetime
import functools
import json
import sys
import time
import redis
from confluent_kafka import Consumer, KafkaError
from config import (
    HEARTBEAT_TTL_SEC,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_GROUP_ID,
    KAFKA_SECURITY_PROTOCOL,
    KAFKA_TOPIC,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_URL,
    get_kafka_consumer_config,
    get_redis_client,
)

# Ensure unbuffered console logging
print = functools.partial(print, flush=True)

TOPIC = KAFKA_TOPIC

print("=" * 60)
print("  Delivery Tracking System - Kafka Location Consumer -> Redis")
print("=" * 60)

# 1. Connect and verify Redis
try:
    r = get_redis_client()
    r.ping()
    redis_target = REDIS_URL.split("@")[-1] if REDIS_URL else f"{REDIS_HOST}:{REDIS_PORT}"
    print(f"[OK] Connected to Redis at {redis_target}")
except Exception as e:
    print(f"[ERROR] Cannot connect to Redis: {e}")
    print("Ensure Redis (local Docker or cloud like Upstash) is reachable.")
    sys.exit(1)

# 2. Connect and configure Kafka Consumer
def on_assign(c, partitions):
    assigned_ids = [p.partition for p in partitions]
    print(f"[OK] Assigned Kafka partitions: {assigned_ids}")
    print("[INFO] Subscribed and actively consuming driver location events...")


try:
    consumer = Consumer(get_kafka_consumer_config())
    meta = consumer.list_topics(timeout=7)
    print(f"[OK] Connected to Kafka ({KAFKA_SECURITY_PROTOCOL}) at {KAFKA_BOOTSTRAP_SERVERS}")
except Exception as e:
    print(f"[ERROR] Cannot connect to Kafka at {KAFKA_BOOTSTRAP_SERVERS}: {e}")
    sys.exit(1)

consumer.subscribe([TOPIC], on_assign=on_assign)

print(f"[INFO] Waiting for messages on topic '{TOPIC}' (Consumer Group: '{KAFKA_GROUP_ID}')...")
print(f"[NOTE] Heartbeat TTL is {HEARTBEAT_TTL_SEC}s. Ensure producer.py is running to stream live pings.\n")

msg_count = 0
idle_ticks = 0
last_idle_notice = 0

try:
    while True:
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            idle_ticks += 1
            # Print periodic reassurance if waiting for producer
            if idle_ticks % 6 == 0 and time.time() - last_idle_notice > 5:
                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                print(
                    f"[{now_str}] Consumer idle — waiting for incoming driver events. "
                    f"(Make sure producer.py is running in another terminal | Total processed so far: {msg_count})"
                )
                last_idle_notice = time.time()
            continue

        idle_ticks = 0

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                # Reached end of partition, normal condition
                continue
            print(f"[ERROR] Kafka consumer error: {msg.error()}")
            continue

        try:
            event = json.loads(msg.value().decode("utf-8"))
        except Exception as json_err:
            print(f"[WARN] Failed to decode message JSON: {json_err}")
            continue

        driver_id = event.get("driver_id")
        lat = event.get("lat")
        lon = event.get("lon")

        if not driver_id or lat is None or lon is None:
            continue

        # Pipeline updates to Redis:
        # 1. Update Geospatial index (lon, lat, member_name)
        # 2. Update Heartbeat key with TTL
        # 3. Store metadata hash for quick lookups
        pipe = r.pipeline()
        pipe.geoadd("drivers:geo", (lon, lat, driver_id))
        pipe.set(f"driver:{driver_id}:alive", 1, ex=HEARTBEAT_TTL_SEC)
        pipe.hset(
            f"driver:{driver_id}:info",
            mapping={
                "lat": str(lat),
                "lon": str(lon),
                "speed_kmh": str(event.get("speed_kmh", 0)),
                "ts": str(event.get("ts", time.time())),
            },
        )
        pipe.expire(f"driver:{driver_id}:info", 120)
        pipe.execute()

        msg_count += 1
        # Log periodically to avoid terminal flooding while keeping clear feedback
        if msg_count % 10 == 0 or msg_count <= 5:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            print(
                f"[{now_str}] Stored in Redis: {driver_id} at ({lat:.4f}, {lon:.4f}) | "
                f"Partition: {msg.partition()} | Total processed: {msg_count}"
            )

except KeyboardInterrupt:
    print(f"\n[INFO] Consumer shutting down. Total events processed: {msg_count}.")
finally:
    consumer.close()
    print("[INFO] Kafka consumer closed cleanly.")
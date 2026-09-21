import datetime
import functools
import json
import random
import sys
import time
from confluent_kafka import Producer
from config import (
    CENTER,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_SECURITY_PROTOCOL,
    KAFKA_TOPIC,
    NUM_DRIVERS,
    get_kafka_producer_config,
)

# Ensure unbuffered console logging
print = functools.partial(print, flush=True)

TOPIC = KAFKA_TOPIC

print("=" * 60)
print("  Delivery Tracking System - Kafka Location Producer")
print("=" * 60)
print(f"Connecting to Kafka ({KAFKA_SECURITY_PROTOCOL}) at: {KAFKA_BOOTSTRAP_SERVERS}")

# Initialize simulated drivers around the center coordinates
drivers = {
    f"driver-{i}": [
        CENTER[0] + random.uniform(-0.04, 0.04),
        CENTER[1] + random.uniform(-0.04, 0.04),
    ]
    for i in range(NUM_DRIVERS)
}

try:
    producer = Producer(get_kafka_producer_config())
    # Test broker connectivity
    meta = producer.list_topics(timeout=7)
    print(f"[OK] Connected to Kafka. Available topics: {list(meta.topics.keys())}")
except Exception as e:
    print(f"[ERROR] Could not connect to Kafka at {KAFKA_BOOTSTRAP_SERVERS}: {e}")
    print("Ensure Kafka broker (local Docker or cloud like Upstash) is reachable.")
    sys.exit(1)

stats = {"delivered": 0, "failed": 0}


def delivery_report(err, msg):
    """Callback triggered by producer.poll() once a message is acknowledged."""
    if err is not None:
        stats["failed"] += 1
        print(f"[FAIL] Delivery failed for driver {msg.key().decode('utf-8')}: {err}")
    else:
        stats["delivered"] += 1


print(f"Simulating {NUM_DRIVERS} active delivery drivers. Emitting GPS pings every 2s...")
print("Press Ctrl+C to stop.\n")

batch_count = 0
try:
    while True:
        batch_count += 1
        start_time = time.time()
        now_str = datetime.datetime.now().strftime("%H:%M:%S")

        for driver_id, pos in drivers.items():
            # Simulate realistic GPS movement jitter
            pos[0] += random.uniform(-0.0004, 0.0004)
            pos[1] += random.uniform(-0.0004, 0.0004)

            event = {
                "driver_id": driver_id,
                "lat": round(pos[0], 6),
                "lon": round(pos[1], 6),
                "speed_kmh": round(random.uniform(15.0, 45.0), 1),
                "ts": time.time(),
            }

            # Retry on BufferError if queue is temporarily full
            queued = False
            for _ in range(5):
                try:
                    producer.produce(
                        TOPIC,
                        key=driver_id,
                        value=json.dumps(event).encode("utf-8"),
                        callback=delivery_report,
                    )
                    queued = True
                    break
                except BufferError:
                    producer.poll(0.1)

            if not queued:
                print(f"[WARN] Local queue full, dropped ping for {driver_id}")

        # Serve delivery callbacks
        producer.poll(0.1)

        print(
            f"[{now_str}] Batch #{batch_count}: Emitted {len(drivers)} pings to '{TOPIC}' | "
            f"Total Delivered: {stats['delivered']} | Failures: {stats['failed']}"
        )
        time.sleep(2)

except KeyboardInterrupt:
    print("\n[INFO] Stopping producer. Flushing outstanding messages to Kafka...")
    remaining = producer.flush(timeout=5)
    print(f"[INFO] Producer stopped. Unflushed messages: {remaining}. Total delivered: {stats['delivered']}.")
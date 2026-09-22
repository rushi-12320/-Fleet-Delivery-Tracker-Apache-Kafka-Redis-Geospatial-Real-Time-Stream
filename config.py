import os
import redis
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

# Web server port
PORT = int(os.getenv("PORT", "8000"))

# Coordinates & Simulation Constants
CENTER = (19.0760, 72.8777)  # Mumbai center
NUM_DRIVERS = int(os.getenv("NUM_DRIVERS", "20"))
HEARTBEAT_TTL_SEC = int(os.getenv("HEARTBEAT_TTL_SEC", "15"))

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256")
KAFKA_SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME", "")
KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "driver-locations")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "location-writer")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_SSL = os.getenv("REDIS_SSL", "false").lower() in ("true", "1", "yes")
REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))


def get_redis_client() -> redis.Redis:
    """Returns a configured Redis client supporting local or cloud (Upstash/Redis Cloud)."""
    if REDIS_URL:
        redis_url = REDIS_URL.strip()
        if redis_url.startswith("redis://") and ("upstash.io" in redis_url.lower() or REDIS_SSL):
            redis_url = redis_url.replace("redis://", "rediss://", 1)
        return redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            retry_on_timeout=True,
        )
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        ssl=REDIS_SSL,
        decode_responses=True,
        socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        retry_on_timeout=True,
    )


def get_kafka_producer_config() -> dict:
    """Builds Kafka Producer configuration with optional SASL_SSL cloud auth."""
    conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "delivery-location-producer",
        "queue.buffering.max.messages": 100000,
        "acks": "all",
    }
    if KAFKA_SECURITY_PROTOCOL.upper() == "SASL_SSL":
        conf.update({
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": KAFKA_SASL_MECHANISM,
            "sasl.username": KAFKA_SASL_USERNAME,
            "sasl.password": KAFKA_SASL_PASSWORD,
        })
    return conf


def get_kafka_consumer_config() -> dict:
    """Builds Kafka Consumer configuration with optional SASL_SSL cloud auth."""
    conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": KAFKA_GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
        "auto.commit.interval.ms": 2000,
        "session.timeout.ms": 6000,
        "heartbeat.interval.ms": 2000,
    }
    if KAFKA_SECURITY_PROTOCOL.upper() == "SASL_SSL":
        conf.update({
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": KAFKA_SASL_MECHANISM,
            "sasl.username": KAFKA_SASL_USERNAME,
            "sasl.password": KAFKA_SASL_PASSWORD,
        })
    return conf

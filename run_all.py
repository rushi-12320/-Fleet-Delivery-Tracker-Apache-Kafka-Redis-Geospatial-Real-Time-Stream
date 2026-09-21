"""
Delivery Tracking System - Unified Service Runner
Launches Producer, Consumer, and FastAPI API server concurrently.
Press Ctrl+C to stop all services cleanly.
"""

import os
import subprocess
import sys
import time

# Set utf-8 output encoding if supported
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PYTHON_EXE = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from config import PORT


def main():
    print("=" * 65)
    print("  Starting Delivery Tracking System (Kafka + Redis + FastAPI)")
    print("=" * 65)

    processes = []

    try:
        # 1. Start Consumer
        print("\n[1/3] Starting Kafka -> Redis Consumer (consumer.py)...")
        p_consumer = subprocess.Popen(
            [PYTHON_EXE, "-u", os.path.join(BASE_DIR, "consumer.py")],
            cwd=BASE_DIR,
        )
        processes.append(("Consumer", p_consumer))
        time.sleep(2)

        # 2. Start Producer
        print("\n[2/3] Starting Simulated GPS Producer (producer.py)...")
        p_producer = subprocess.Popen(
            [PYTHON_EXE, "-u", os.path.join(BASE_DIR, "producer.py")],
            cwd=BASE_DIR,
        )
        processes.append(("Producer", p_producer))
        time.sleep(1)

        # 3. Start API Server
        print(f"\n[3/3] Starting FastAPI Server on port {PORT}...")
        p_api = subprocess.Popen(
            [
                PYTHON_EXE,
                "-m",
                "uvicorn",
                "api:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(PORT),
            ],
            cwd=BASE_DIR,
        )
        processes.append(("API Server", p_api))

        print("\n" + "=" * 65)
        print("  All services running successfully!")
        print(f"  Dashboard: http://localhost:{PORT}")
        print(f"  Health:    http://localhost:{PORT}/health")
        print(f"  API:       http://localhost:{PORT}/drivers/nearby?lat=19.076&lon=72.877")
        print("=" * 65)
        print("\nPress Ctrl+C anytime to cleanly stop all services...\n")

        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"[WARN] {name} exited unexpectedly with code {ret}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping all services...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"[INFO] Terminating {name}...")
                proc.terminate()
        for name, proc in processes:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("[OK] All processes stopped cleanly.")


if __name__ == "__main__":
    main()

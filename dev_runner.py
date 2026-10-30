import os
import sys
import time
import subprocess
import signal

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVICES = [
    {"name": "Auth Service", "module": "services.auth.main:app", "port": 8001},
    {"name": "Catalog Service", "module": "services.catalog.main:app", "port": 8002},
    {"name": "Search & Cache Service", "module": "services.search.main:app", "port": 8003, "env": {"CATALOG_URL": "http://127.0.0.1:8002"}},
    {"name": "Cart Service", "module": "services.cart.main:app", "port": 8004},
    {"name": "Order Service", "module": "services.order.main:app", "port": 8005, "env": {
        "CATALOG_URL": "http://127.0.0.1:8002",
        "NOTIFICATION_URL": "http://127.0.0.1:8009",
        "AUDIT_URL": "http://127.0.0.1:8012"
    }},
    {"name": "Payment Service", "module": "services.payment.main:app", "port": 8006, "env": {
        "ORDER_URL": "http://127.0.0.1:8005",
        "NOTIFICATION_URL": "http://127.0.0.1:8009",
        "AUDIT_URL": "http://127.0.0.1:8012"
    }},
    {"name": "Review Service", "module": "services.review.main:app", "port": 8007},
    {"name": "Recommendation Service", "module": "services.recommendation.main:app", "port": 8008, "env": {"CATALOG_URL": "http://127.0.0.1:8002"}},
    {"name": "Notification Service", "module": "services.notification.main:app", "port": 8009},
    {"name": "Analytics Service", "module": "services.analytics.main:app", "port": 8010, "env": {
        "ORDER_URL": "http://127.0.0.1:8005",
        "CATALOG_URL": "http://127.0.0.1:8002"
    }},
    {"name": "Support Service", "module": "services.support.main:app", "port": 8011},
    {"name": "Audit Service", "module": "services.audit.main:app", "port": 8012},
    {"name": "API Gateway", "module": "gateway.local_gateway:app", "port": 80}
]

processes = []

def cleanup(sig=None, frame=None):
    print("\n🛑 Shutting down all 12 microservices and API Gateway...")
    for p in processes:
        try:
            p.terminate()
            p.kill()
        except Exception:
            pass
    print("✅ All services stopped safely.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    # Detect venv python
    venv_py = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
    python_cmd = venv_py if os.path.exists(venv_py) else sys.executable

    print("=" * 65)
    print("🚀 LAUNCHING 12 MICROSERVICES + API GATEWAY (PAD LAB 2)")
    print("=" * 65)

    env_base = os.environ.copy()
    env_base["PYTHONPATH"] = root_dir

    for s in SERVICES:
        env = env_base.copy()
        if "env" in s:
            env.update(s["env"])

        cmd = [
            python_cmd, "-m", "uvicorn",
            s["module"],
            "--host", "0.0.0.0",
            "--port", str(s["port"]),
            "--log-level", "warning"
        ]

        p = subprocess.Popen(cmd, env=env)
        processes.append(p)
        print(f"  ⚡ [{s['port']}] {s['name']:<28} -> Running")
        time.sleep(0.15)

    print("=" * 65)
    print("🎉 ALL 12 MICROSERVICES ARE ACTIVE!")
    print("🌐 Web UI & API Gateway: http://localhost:80")
    print("🛡️ Cloudflare Tunnel should target: http://localhost:80")
    print("Press Ctrl+C to shut down.")
    print("=" * 65)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()

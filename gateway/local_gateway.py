import os
import time
from typing import List, Dict
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI(title="Local API Gateway & Reverse Proxy", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICE_ROUTES = {
    "/api/auth": "http://127.0.0.1:8001",
    "/api/catalog": "http://127.0.0.1:8002",
    "/api/search": "http://127.0.0.1:8003",
    "/api/cart": "http://127.0.0.1:8004",
    "/api/orders": "http://127.0.0.1:8005",
    "/api/payments": "http://127.0.0.1:8006",
    "/api/reviews": "http://127.0.0.1:8007",
    "/api/recommendations": "http://127.0.0.1:8008",
    "/api/notifications": "http://127.0.0.1:8009",
    "/api/analytics": "http://127.0.0.1:8010",
    "/api/support": "http://127.0.0.1:8011",
    "/api/audit": "http://127.0.0.1:8012",
}

# In-Memory Ring Buffer for Real-Time Traffic Telemetry
TRAFFIC_LOGS: List[Dict] = []
MAX_TRAFFIC_LOGS = 200

client = httpx.AsyncClient(timeout=10.0)

# Live Traffic Telemetry Streams
@app.get("/api/stream/traffic")
@app.get("/stream/traffic")
async def get_traffic(limit: int = 60):
    return TRAFFIC_LOGS[-limit:]

@app.delete("/api/stream/traffic")
@app.delete("/stream/traffic")
async def clear_traffic():
    TRAFFIC_LOGS.clear()
    return {"status": "cleared"}

# OpenAPI Docs Index
@app.get("/docs", response_class=HTMLResponse)
async def get_all_docs():
    links_html = "".join([
        f'<li style="margin-bottom:8px;"><a href="/docs/{s}" style="color:#3b82f6;text-decoration:none;font-family:JetBrains Mono, monospace;font-size:15px;">/docs/{s} &rarr; {s}-service</a></li>'
        for s in ["auth", "catalog", "search", "cart", "orders", "payments", "reviews", "recommendations", "notifications", "analytics", "support", "audit"]
    ])
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CloudMart Microservices • API Specs</title>
    <style>
        body {{ background: #000; color: #ededed; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 48px; line-height: 1.6; }}
        h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 24px; }}
        ul {{ list-style: none; padding: 0; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Microservices OpenAPI Documentation</h1>
    <ul>{links_html}</ul>
    <p style="margin-top: 32px;"><a href="/" style="color: #10b981; font-size: 14px; text-decoration: none;">&larr; Back to CloudMart App</a></p>
</body>
</html>"""

# Public OpenAPI Docs Proxy per Service
@app.get("/docs/{service_name}", response_class=HTMLResponse)
async def get_service_swagger(service_name: str):
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{service_name} • OpenAPI Documentation</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body {{ margin: 0; padding: 0; background: #0b0b0e; color: #fff; }}
        .swagger-ui {{ filter: invert(88%) hue-rotate(180deg); }}
        .swagger-ui .topbar {{ display: none; }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({{
            url: '/api/{service_name}/openapi.json',
            dom_id: '#swagger-ui',
            presets: [SwaggerUIBundle.presets.apis],
            layout: "BaseLayout"
        }});
    </script>
</body>
</html>"""

@app.api_route("/api/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def reverse_proxy(service_name: str, path: str, request: Request):
    key = f"/api/{service_name}"
    target_host = SERVICE_ROUTES.get(key)
    if not target_host:
        return Response(content=f"Unknown service '{service_name}'", status_code=404)

    target_url = f"{target_host}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    req_headers = dict(request.headers)
    req_headers.pop("host", None)

    body = await request.body()
    start_time = time.time()
    status_code = 500
    res_bytes = b""
    res_headers = {}
    x_cache = "-"

    try:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=req_headers,
            content=body
        )
        status_code = resp.status_code
        res_bytes = resp.content
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        res_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        x_cache = resp.headers.get("x-cache", resp.headers.get("X-Cache", "-"))
    except Exception as e:
        res_bytes = f"Gateway routing error to {service_name}: {str(e)}".encode()
        status_code = 502

    latency_ms = round((time.time() - start_time) * 1000, 2)

    # Record into Traffic Telemetry Ring Buffer
    try:
        body_snippet = body.decode("utf-8", errors="ignore")[:300] if body else ""
    except Exception:
        body_snippet = ""

    TRAFFIC_LOGS.append({
        "id": f"req_{int(time.time() * 1000)}_{len(TRAFFIC_LOGS)}",
        "timestamp": time.time(),
        "time_str": time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}",
        "method": request.method,
        "path": f"/api/{service_name}/{path}" + (f"?{request.url.query}" if request.url.query else ""),
        "service": service_name,
        "target": target_url,
        "status": status_code,
        "latency_ms": latency_ms,
        "cache": x_cache,
        "body_preview": body_snippet,
        "hop": f"Client -> Gateway :80 -> {service_name} ({target_host.replace('http://', '')}) -> {status_code}"
    })

    if len(TRAFFIC_LOGS) > MAX_TRAFFIC_LOGS:
        TRAFFIC_LOGS.pop(0)

    return Response(content=res_bytes, status_code=status_code, headers=res_headers)

# Serve Frontend static files with no-cache headers
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/style.css")
async def get_css():
    css_path = os.path.join(FRONTEND_DIR, "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="text/css",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"}
    )

@app.get("/app.js")
async def get_js():
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"}
    )

if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

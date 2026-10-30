# CloudMart Distributed: 12-Microservices E-Commerce Platform

Laboratory Work №2 on **PAD (Distributed Applications Programming / Programarea Aplicațiilor Distribuite)**.  
Technical University of Moldova (FCIM UTM), Group TI-235.

---

## 🏛️ Architecture Overview

The system consists of **12 decoupled microservices** fronted by an **API Gateway (Reverse Proxy)** and backed by **Redis Caching**:

| № | Service | Port | Architectural Pattern | Primary Responsibility |
|---|---|---|---|---|
| **0** | **API Gateway** | `80` | Reverse Proxy / Unified Ingress | Routes public requests, handles CORS, serves Frontend SPA |
| **1** | **auth-service** | `8001` | JWT Security / Claims | User registration, login, role authorization |
| **2** | **catalog-service** | `8002` | Repository + Domain Service | Product CRUD, hardware catalog, stock quantity management |
| **3** | **search-service** | `8003` | Cache-Aside (Redis / TTL) | Fast multi-attribute search with `X-Cache: HIT/MISS` headers |
| **4** | **cart-service** | `8004` | Key-Value Session State | User shopping cart persistence |
| **5** | **order-service** | `8005` | State Machine + Events | Order placement, state transitions (`PENDING` $\to$ `PAID`) |
| **6** | **payment-service** | `8006` | Transaction Ledger | Card validation, mock payment gateway, financial audit |
| **7** | **review-service** | `8007` | Aggregator Pattern | 1-5 star ratings, customer feedback & distribution metrics |
| **8** | **recommendation-service** | `8008` | Content-Based Similarity | Category/tag affinity scoring for related hardware |
| **9** | **notification-service** | `8009` | Asynchronous Event Log | Dispatches order confirmations & payment receipts |
| **10**| **analytics-service** | `8010` | Cross-Service Query | Aggregates revenue, AOV, top-selling items for BI dashboard |
| **11**| **support-service** | `8011` | Conversation Threading | Customer helpdesk tickets and interactive messages |
| **12**| **audit-service** | `8012` | Centralized Security Ledger | Immutable chronological audit trail of all business events |

---

## 🚀 How to Run

### Option 1: Native Windows (Instant 1-Click Launch)
```cmd
run_local.bat
```
*(Runs all 12 services and API Gateway via Python virtual environment on `http://localhost:80`)*

### Option 2: Docker Compose (Full Containerization)
```cmd
run_docker.bat
```
*(Builds and runs all 12 containers, Redis, and Nginx in Docker network `pad-network`)*

### Option 3: Cloudflare Public Tunnel
```cmd
run_tunnel.bat
```
*(Proxies `http://localhost:80` to your Cloudflare Zero Trust public hostname)*

---

## 📚 Architectural Patterns & Principles Implemented

* **Decoupled Architecture:** 12 microservices with strict Database-per-Service data isolation (zero shared tables or files).
* **Caching Layer:** Cache-Aside strategy with deterministic TTL expiration and `X-Cache: HIT / MISS` telemetry.
* **Unified Ingress:** API Gateway reverse proxy on port `:80` unifying cross-service routing and telemetry streaming.
* **Frontend MVVM:** Model-View-ViewModel presentation layer separating reactive state mutations from DOM rendering.
* **Inter-Service Communication:** Synchronous REST calls using resilient HTTP clients with timeouts and fallback error handling.

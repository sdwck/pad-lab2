import os
import time
from typing import Dict, List
import httpx
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ORDER_URL = os.getenv("ORDER_URL", "http://order-service:8005")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-service:8002")

class TopProduct(BaseModel):
    product_id: str
    title: str
    units_sold: int
    revenue: float

class DashboardMetrics(BaseModel):
    total_revenue: float
    total_orders: int
    average_order_value: float
    paid_orders_count: int
    pending_orders_count: int
    total_catalog_products: int
    top_products: List[TopProduct]
    computed_at: float

# --- Repository / Gateway for Analytics ---
class AggregatedDataRepository:
    def __init__(self, order_url: str = ORDER_URL, catalog_url: str = CATALOG_URL):
        self.order_url = order_url
        self.catalog_url = catalog_url

    async def fetch_orders(self) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.order_url}/orders")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return []

    async def fetch_products(self) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.catalog_url}/products")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return []

# --- Service Layer Pattern ---
class AnalyticsService:
    def __init__(self, repo: AggregatedDataRepository):
        self.repo = repo

    async def compute_dashboard_metrics(self) -> DashboardMetrics:
        orders = await self.repo.fetch_orders()
        products = await self.repo.fetch_products()

        paid_orders = [o for o in orders if o.get("status") in ["PAID", "PROCESSING", "SHIPPED", "COMPLETED"]]
        total_rev = round(sum(o.get("total_amount", 0) for o in paid_orders), 2)
        total_count = len(orders)
        aov = round(total_rev / len(paid_orders), 2) if paid_orders else 0.0

        # Tally top products
        sold_map: Dict[str, dict] = {}
        for o in paid_orders:
            for it in o.get("items", []):
                pid = it.get("product_id")
                qty = it.get("quantity", 1)
                price = it.get("price", 0)
                if pid not in sold_map:
                    sold_map[pid] = {
                        "product_id": pid,
                        "title": it.get("title", pid),
                        "units_sold": 0,
                        "revenue": 0.0
                    }
                sold_map[pid]["units_sold"] += qty
                sold_map[pid]["revenue"] = round(sold_map[pid]["revenue"] + (price * qty), 2)

        top_list = sorted(list(sold_map.values()), key=lambda x: x["revenue"], reverse=True)[:5]
        top_prods = [TopProduct(**t) for t in top_list]

        return DashboardMetrics(
            total_revenue=total_rev,
            total_orders=total_count,
            average_order_value=aov,
            paid_orders_count=len(paid_orders),
            pending_orders_count=len([o for o in orders if o.get("status") == "PENDING_PAYMENT"]),
            total_catalog_products=len(products),
            top_products=top_prods,
            computed_at=time.time()
        )

# --- FastAPI App & DI ---
app = FastAPI(title="Business Intelligence & Analytics Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> AggregatedDataRepository:
    return AggregatedDataRepository()

def get_service(repo: AggregatedDataRepository = Depends(get_repo)) -> AnalyticsService:
    return AnalyticsService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service", "version": "2.0.0"}

@app.get("/analytics/dashboard", response_model=DashboardMetrics)
async def get_dashboard(service: AnalyticsService = Depends(get_service)):
    return await service.compute_dashboard_metrics()

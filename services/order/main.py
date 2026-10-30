import json
import os
import time
from typing import Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/orders.json" if os.path.exists("/data") else "orders_data.json")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-service:8002")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification-service:8009")
AUDIT_URL = os.getenv("AUDIT_URL", "http://audit-service:8012")

class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    shipping_address: str
    customer_name: str
    customer_email: str

class OrderStatusUpdate(BaseModel):
    status: str  # PENDING_PAYMENT, PAID, PROCESSING, SHIPPED, COMPLETED, CANCELLED

class Order(BaseModel):
    id: str
    user_id: str
    customer_name: str
    customer_email: str
    shipping_address: str
    items: List[OrderItem]
    total_amount: float
    status: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

# --- Repository Pattern ---
class OrderRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            sample_order = {
                "ord_1001": {
                    "id": "ord_1001",
                    "user_id": "user_demo",
                    "customer_name": "Tima Diaconu",
                    "customer_email": "student@utm.md",
                    "shipping_address": "Str. Studenților 9/7, Chișinău",
                    "items": [
                        {
                            "product_id": "prod_3",
                            "title": "Keychron Q1 Pro Wireless Custom Keyboard",
                            "price": 199.99,
                            "quantity": 1
                        }
                    ],
                    "total_amount": 199.99,
                    "status": "PAID",
                    "created_at": time.time() - 86400,
                    "updated_at": time.time() - 86400
                }
            }
            self._save(sample_order)

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_by_id(self, order_id: str) -> Optional[dict]:
        return self._load().get(order_id)

    def get_by_user(self, user_id: str) -> List[dict]:
        orders = self._load().values()
        user_orders = [o for o in orders if o.get("user_id") == user_id]
        user_orders.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return user_orders

    def get_all(self) -> List[dict]:
        orders = list(self._load().values())
        orders.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return orders

    def save(self, order_data: dict):
        orders = self._load()
        orders[order_data["id"]] = order_data
        self._save(orders)

# --- Service Layer Pattern ---
class OrderService:
    def __init__(self, repo: OrderRepository):
        self.repo = repo

    async def create_order(self, dto: OrderCreate) -> Order:
        if not dto.items:
            raise HTTPException(status_code=400, detail="Cannot create an empty order")

        total = round(sum(i.price * i.quantity for i in dto.items), 2)
        order_id = f"ord_{int(time.time() * 1000)}"

        order_record = {
            "id": order_id,
            "user_id": dto.user_id,
            "customer_name": dto.customer_name,
            "customer_email": dto.customer_email,
            "shipping_address": dto.shipping_address,
            "items": [i.model_dump() for i in dto.items],
            "total_amount": total,
            "status": "PENDING_PAYMENT",
            "created_at": time.time(),
            "updated_at": time.time()
        }

        self.repo.save(order_record)

        # Inter-service calls: notify & audit
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                # 1. Audit event
                await client.post(f"{AUDIT_URL}/audit/log", json={
                    "service": "order-service",
                    "action": "ORDER_CREATED",
                    "user_id": dto.user_id,
                    "details": f"Order {order_id} created for {total} USD"
                })
                # 2. Notification event
                await client.post(f"{NOTIFICATION_URL}/notifications/send", json={
                    "user_id": dto.user_id,
                    "title": "Order Placed",
                    "message": f"Your order #{order_id} has been placed. Please complete payment.",
                    "type": "order"
                })
        except Exception:
            pass

        return Order(**order_record)

    async def update_status(self, order_id: str, new_status: str) -> Order:
        raw = self.repo.get_by_id(order_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Order not found")

        valid_statuses = ["PENDING_PAYMENT", "PAID", "PROCESSING", "SHIPPED", "COMPLETED", "CANCELLED"]
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {valid_statuses}")

        raw["status"] = new_status
        raw["updated_at"] = time.time()
        self.repo.save(raw)

        # Notify user of status change
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                await client.post(f"{NOTIFICATION_URL}/notifications/send", json={
                    "user_id": raw["user_id"],
                    "title": f"Order #{order_id} Updated",
                    "message": f"Status changed to: {new_status}",
                    "type": "order"
                })
        except Exception:
            pass

        return Order(**raw)

    def get_order(self, order_id: str) -> Order:
        raw = self.repo.get_by_id(order_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Order not found")
        return Order(**raw)

    def get_user_orders(self, user_id: str) -> List[Order]:
        return [Order(**o) for o in self.repo.get_by_user(user_id)]

    def get_all_orders(self) -> List[Order]:
        return [Order(**o) for o in self.repo.get_all()]

# --- FastAPI App & DI ---
app = FastAPI(title="Order Management Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> OrderRepository:
    return OrderRepository()

def get_service(repo: OrderRepository = Depends(get_repo)) -> OrderService:
    return OrderService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service", "version": "2.0.0"}

@app.post("/orders", response_model=Order)
async def create_order(dto: OrderCreate, service: OrderService = Depends(get_service)):
    return await service.create_order(dto)

@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str, service: OrderService = Depends(get_service)):
    return service.get_order(order_id)

@app.get("/orders/user/{user_id}", response_model=List[Order])
def list_user_orders(user_id: str, service: OrderService = Depends(get_service)):
    return service.get_user_orders(user_id)

@app.patch("/orders/{order_id}/status", response_model=Order)
async def update_order_status(order_id: str, dto: OrderStatusUpdate, service: OrderService = Depends(get_service)):
    return await service.update_status(order_id, dto.status)

@app.get("/orders", response_model=List[Order])
def list_all_orders(service: OrderService = Depends(get_service)):
    return service.get_all_orders()

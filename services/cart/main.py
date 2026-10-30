import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/cart.json" if os.path.exists("/data") else "cart_data.json")

class CartItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(ge=1)
    image_url: str = ""

class Cart(BaseModel):
    user_id: str
    items: List[CartItem] = []
    total_price: float = 0.0
    items_count: int = 0
    updated_at: float = Field(default_factory=time.time)

class AddItemDto(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = 1
    image_url: str = ""

class UpdateQuantityDto(BaseModel):
    quantity: int = Field(ge=1)

# --- Repository Pattern ---
class CartRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            self._save({})

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_cart(self, user_id: str) -> dict:
        data = self._load()
        if user_id not in data:
            data[user_id] = {
                "user_id": user_id,
                "items": [],
                "updated_at": time.time()
            }
            self._save(data)
        return data[user_id]

    def save_cart(self, user_id: str, cart_data: dict):
        data = self._load()
        cart_data["updated_at"] = time.time()
        data[user_id] = cart_data
        self._save(data)

    def clear_cart(self, user_id: str):
        data = self._load()
        if user_id in data:
            data[user_id] = {
                "user_id": user_id,
                "items": [],
                "updated_at": time.time()
            }
            self._save(data)

# --- Service Layer Pattern ---
class CartService:
    def __init__(self, repo: CartRepository):
        self.repo = repo

    def _calculate(self, raw: dict) -> Cart:
        items = [CartItem(**i) for i in raw.get("items", [])]
        total = round(sum(i.price * i.quantity for i in items), 2)
        count = sum(i.quantity for i in items)
        return Cart(
            user_id=raw["user_id"],
            items=items,
            total_price=total,
            items_count=count,
            updated_at=raw.get("updated_at", time.time())
        )

    def get_user_cart(self, user_id: str) -> Cart:
        raw = self.repo.get_cart(user_id)
        return self._calculate(raw)

    def add_item(self, user_id: str, dto: AddItemDto) -> Cart:
        raw = self.repo.get_cart(user_id)
        items = raw.get("items", [])
        
        fallback_img = "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=500&auto=format&fit=crop&q=60"
        item_img = dto.image_url if dto.image_url and dto.image_url.strip() else fallback_img

        found = False
        for item in items:
            if item["product_id"] == dto.product_id:
                item["quantity"] += dto.quantity
                if not item.get("image_url"):
                    item["image_url"] = item_img
                found = True
                break
        
        if not found:
            items.append({
                "product_id": dto.product_id,
                "title": dto.title,
                "price": dto.price,
                "quantity": dto.quantity,
                "image_url": item_img
            })
        
        raw["items"] = items
        self.repo.save_cart(user_id, raw)
        return self._calculate(raw)

    def update_quantity(self, user_id: str, product_id: str, qty: int) -> Cart:
        raw = self.repo.get_cart(user_id)
        items = raw.get("items", [])
        
        for item in items:
            if item["product_id"] == product_id:
                item["quantity"] = qty
                break
        
        raw["items"] = items
        self.repo.save_cart(user_id, raw)
        return self._calculate(raw)

    def remove_item(self, user_id: str, product_id: str) -> Cart:
        raw = self.repo.get_cart(user_id)
        raw["items"] = [i for i in raw.get("items", []) if i["product_id"] != product_id]
        self.repo.save_cart(user_id, raw)
        return self._calculate(raw)

    def clear(self, user_id: str) -> Cart:
        self.repo.clear_cart(user_id)
        return Cart(user_id=user_id, items=[], total_price=0.0, items_count=0)

# --- FastAPI App & DI ---
app = FastAPI(title="Shopping Cart Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> CartRepository:
    return CartRepository()

def get_service(repo: CartRepository = Depends(get_repo)) -> CartService:
    return CartService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "cart-service", "version": "2.0.0"}

@app.get("/cart/{user_id}", response_model=Cart)
def get_cart(user_id: str, service: CartService = Depends(get_service)):
    return service.get_user_cart(user_id)

@app.post("/cart/{user_id}/items", response_model=Cart)
def add_item(user_id: str, dto: AddItemDto, service: CartService = Depends(get_service)):
    return service.add_item(user_id, dto)

@app.put("/cart/{user_id}/items/{product_id}", response_model=Cart)
def update_item_quantity(user_id: str, product_id: str, dto: UpdateQuantityDto, service: CartService = Depends(get_service)):
    return service.update_quantity(user_id, product_id, dto.quantity)

@app.delete("/cart/{user_id}/items/{product_id}", response_model=Cart)
def remove_item(user_id: str, product_id: str, service: CartService = Depends(get_service)):
    return service.remove_item(user_id, product_id)

@app.delete("/cart/{user_id}", response_model=Cart)
def clear_cart(user_id: str, service: CartService = Depends(get_service)):
    return service.clear(user_id)

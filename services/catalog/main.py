import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/catalog.json" if os.path.exists("/data") else "catalog_data.json")

# --- Domain Models ---
class Product(BaseModel):
    id: str
    title: str
    category: str
    price: float
    stock: int
    rating: float = 4.8
    reviews_count: int = 12
    description: str
    image_url: str
    tags: List[str] = []
    created_at: float = Field(default_factory=time.time)

class ProductCreate(BaseModel):
    title: str
    category: str
    price: float
    stock: int
    description: str
    image_url: str
    tags: List[str] = []

class StockUpdate(BaseModel):
    quantity_delta: int  # e.g. -1 when bought, +10 when restocked

# --- Repository Pattern ---
class ProductRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            initial_products = [
                {
                    "id": "prod_1",
                    "title": "MacBook Pro 16\" M3 Max",
                    "category": "Laptops",
                    "price": 3499.00,
                    "stock": 14,
                    "rating": 4.9,
                    "reviews_count": 38,
                    "description": "Apple M3 Max 16-core CPU, 40-core GPU, 48GB Unified RAM, 1TB NVMe.",
                    "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600&auto=format&fit=crop&q=80",
                    "tags": ["apple", "m3", "laptop", "silicon"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_2",
                    "title": "NVIDIA GeForce RTX 4090 OC",
                    "category": "Components",
                    "price": 1999.00,
                    "stock": 6,
                    "rating": 5.0,
                    "reviews_count": 42,
                    "description": "24GB GDDR6X, Ada Lovelace, 4th gen Tensor Cores for local LLM inference.",
                    "image_url": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=600&auto=format&fit=crop&q=80",
                    "tags": ["gpu", "nvidia", "hardware", "ai"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_3",
                    "title": "Keychron Q1 Pro Wireless",
                    "category": "Peripherals",
                    "price": 199.99,
                    "stock": 25,
                    "rating": 4.8,
                    "reviews_count": 56,
                    "description": "CNC aluminum chassis, double-gasket acoustic mount, hot-swappable switches.",
                    "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop&q=80",
                    "tags": ["keyboard", "mechanical", "custom"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_4",
                    "title": "Dell UltraSharp 32\" 4K Hub (U3223QE)",
                    "category": "Monitors",
                    "price": 849.50,
                    "stock": 11,
                    "rating": 4.7,
                    "reviews_count": 19,
                    "description": "IPS Black panel, 2000:1 contrast, 90W USB-C Power Delivery, RJ45 Ethernet.",
                    "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600&auto=format&fit=crop&q=80",
                    "tags": ["monitor", "4k", "ips", "usb-c"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_5",
                    "title": "Sony WH-1000XM5 ANC",
                    "category": "Audio",
                    "price": 398.00,
                    "stock": 18,
                    "rating": 4.9,
                    "reviews_count": 76,
                    "description": "Dual processor ANC engine, 8 microphones, 30h battery life, LDAC Hi-Res.",
                    "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80",
                    "tags": ["audio", "anc", "wireless", "headphones"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_6",
                    "title": "Raspberry Pi 5 (8GB Edition)",
                    "category": "IoT & Servers",
                    "price": 85.00,
                    "stock": 42,
                    "rating": 4.8,
                    "reviews_count": 64,
                    "description": "Broadcom BCM2712 Quad Arm Cortex-A76 @ 2.4GHz, dual 4Kp60, PCIe 2.0 slot.",
                    "image_url": "https://images.unsplash.com/photo-1629654297299-c8506221ca97?w=600&auto=format&fit=crop&q=80",
                    "tags": ["arm", "iot", "linux", "edge"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_7",
                    "title": "Apple Mac Studio M2 Ultra",
                    "category": "Workstations",
                    "price": 3999.00,
                    "stock": 5,
                    "rating": 5.0,
                    "reviews_count": 28,
                    "description": "24-core CPU, 60-core GPU, 64GB Unified RAM, 800GB/s bandwidth, 1TB SSD.",
                    "image_url": "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?w=600&auto=format&fit=crop&q=80",
                    "tags": ["apple", "mac", "workstation", "silicon"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_8",
                    "title": "Samsung 990 PRO NVMe 4TB",
                    "category": "Components",
                    "price": 319.99,
                    "stock": 30,
                    "rating": 4.9,
                    "reviews_count": 83,
                    "description": "PCIe 4.0 NVMe M.2 2280, up to 7450 MB/s sequential read, nickel heat spreader.",
                    "image_url": "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=600&auto=format&fit=crop&q=80",
                    "tags": ["ssd", "nvme", "pcie", "storage"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_9",
                    "title": "Ubiquiti UniFi Dream Machine Pro",
                    "category": "Networking",
                    "price": 499.00,
                    "stock": 14,
                    "rating": 4.8,
                    "reviews_count": 35,
                    "description": "Enterprise 10G SFP+ Gateway, 3.5 Gbps IDS/IPS throughput, 8-port GbE switch.",
                    "image_url": "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=600&auto=format&fit=crop&q=80",
                    "tags": ["networking", "unifi", "enterprise", "router"],
                    "created_at": time.time()
                },
                {
                    "id": "prod_10",
                    "title": "Logitech MX Master 3S",
                    "category": "Peripherals",
                    "price": 99.99,
                    "stock": 50,
                    "rating": 4.9,
                    "reviews_count": 112,
                    "description": "8K DPI any-surface track sensor, Quiet Clicks, MagSpeed electromagnetic scroll.",
                    "image_url": "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=600&auto=format&fit=crop&q=80",
                    "tags": ["mouse", "wireless", "logitech", "ergonomic"],
                    "created_at": time.time()
                }
            ]
            self._save({p["id"]: p for p in initial_products})

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_all(self) -> List[dict]:
        return list(self._load().values())

    def get_by_id(self, product_id: str) -> Optional[dict]:
        return self._load().get(product_id)

    def save(self, product: dict):
        items = self._load()
        items[product["id"]] = product
        self._save(items)

# --- Service Layer Pattern ---
class CatalogService:
    def __init__(self, repo: ProductRepository):
        self.repo = repo

    def list_products(self, category: Optional[str] = None) -> List[Product]:
        items = self.repo.get_all()
        if category:
            items = [i for i in items if i.get("category", "").lower() == category.lower()]
        return [Product(**i) for i in items]

    def get_product(self, product_id: str) -> Product:
        item = self.repo.get_by_id(product_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Product with id '{product_id}' not found")
        return Product(**item)

    def create_product(self, dto: ProductCreate) -> Product:
        pid = f"prod_{int(time.time() * 1000)}"
        new_prod = {
            "id": pid,
            "title": dto.title,
            "category": dto.category,
            "price": dto.price,
            "stock": dto.stock,
            "rating": 5.0,
            "reviews_count": 0,
            "description": dto.description,
            "image_url": dto.image_url,
            "tags": dto.tags,
            "created_at": time.time()
        }
        self.repo.save(new_prod)
        return Product(**new_prod)

    def update_stock(self, product_id: str, delta: int) -> Product:
        item = self.repo.get_by_id(product_id)
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        if item["stock"] + delta < 0:
            raise HTTPException(status_code=400, detail="Insufficient stock for this product")
        item["stock"] += delta
        self.repo.save(item)
        return Product(**item)

    def get_categories(self) -> List[str]:
        items = self.repo.get_all()
        cats = sorted(list({i.get("category") for i in items if i.get("category")}))
        return cats

# --- FastAPI App & DI ---
app = FastAPI(title="Product Catalog Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> ProductRepository:
    return ProductRepository()

def get_service(repo: ProductRepository = Depends(get_repo)) -> CatalogService:
    return CatalogService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "catalog-service", "version": "2.0.0"}

@app.get("/products", response_model=List[Product])
def list_products(category: Optional[str] = None, service: CatalogService = Depends(get_service)):
    return service.list_products(category)

@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str, service: CatalogService = Depends(get_service)):
    return service.get_product(product_id)

@app.post("/products", response_model=Product)
def create_product(dto: ProductCreate, service: CatalogService = Depends(get_service)):
    return service.create_product(dto)

@app.put("/products/{product_id}/stock", response_model=Product)
def update_stock(product_id: str, dto: StockUpdate, service: CatalogService = Depends(get_service)):
    return service.update_stock(product_id, dto.quantity_delta)

@app.get("/categories", response_model=List[str])
def list_categories(service: CatalogService = Depends(get_service)):
    return service.get_categories()

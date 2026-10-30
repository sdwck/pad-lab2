import json
import os
import time
from typing import List, Optional
import httpx
from fastapi import FastAPI, Depends, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-service:8002")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# --- In-Memory Cache with TTL (Redis fallback) ---
class CacheManager:
    def __init__(self):
        self._memory_cache = {}
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        try:
            import redis
            self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
            self.redis_client.ping()
        except Exception:
            self.redis_client = None

    def get(self, key: str) -> Optional[str]:
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception:
                pass
        
        entry = self._memory_cache.get(key)
        if entry:
            val, exp = entry
            if time.time() < exp:
                return val
            del self._memory_cache[key]
        return None

    def set(self, key: str, value: str, ttl: int = 30):
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
                return
            except Exception:
                pass
        self._memory_cache[key] = (value, time.time() + ttl)

cache = CacheManager()

# --- Models ---
class SearchResult(BaseModel):
    query: str
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort_by: Optional[str] = None
    total_matches: int
    items: List[dict]
    cached: bool
    latency_ms: float
    cache_backend: str

# --- Repository: Queries Catalog Service ---
class CatalogClientRepository:
    def __init__(self, catalog_url: str = CATALOG_URL):
        self.catalog_url = catalog_url

    async def fetch_all_products(self) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.catalog_url}/products")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        # Fallback in case catalog is unreachable during local test
        return []

# --- Service: Search, Filter, Sort and Cache ---
class SearchService:
    def __init__(self, repo: CatalogClientRepository):
        self.repo = repo

    async def search(
        self,
        q: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        tag: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> tuple[SearchResult, bool]:
        start = time.time()
        cache_key = f"search:{q}:{category}:{min_price}:{max_price}:{tag}:{sort_by}"
        cached_data = cache.get(cache_key)

        backend_name = "Redis" if cache.redis_client else "In-Memory TTL"

        if cached_data:
            result_dict = json.loads(cached_data)
            elapsed = round((time.time() - start) * 1000, 2)
            result = SearchResult(
                **result_dict,
                cached=True,
                latency_ms=elapsed,
                cache_backend=backend_name
            )
            return result, True

        products = await self.repo.fetch_all_products()
        filtered = []

        q_lower = q.lower().strip()
        for p in products:
            # Query match
            if q_lower:
                title = p.get("title", "").lower()
                desc = p.get("description", "").lower()
                tags = [t.lower() for t in p.get("tags", [])]
                if q_lower not in title and q_lower not in desc and not any(q_lower in t for t in tags):
                    continue

            # Category filter
            if category and p.get("category", "").lower() != category.lower():
                continue

            # Price filter
            price = p.get("price", 0)
            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue

            # Tag filter
            if tag and tag.lower() not in [t.lower() for t in p.get("tags", [])]:
                continue

            filtered.append(p)

        # Sorting
        if sort_by == "price_asc":
            filtered.sort(key=lambda x: x.get("price", 0))
        elif sort_by == "price_desc":
            filtered.sort(key=lambda x: x.get("price", 0), reverse=True)
        elif sort_by == "rating_desc":
            filtered.sort(key=lambda x: x.get("rating", 0), reverse=True)

        elapsed = round((time.time() - start) * 1000, 2)
        payload = {
            "query": q,
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "sort_by": sort_by,
            "total_matches": len(filtered),
            "items": filtered
        }

        # Cache for 20 seconds
        cache.set(cache_key, json.dumps(payload), ttl=20)

        result = SearchResult(
            **payload,
            cached=False,
            latency_ms=elapsed,
            cache_backend=backend_name
        )
        return result, False

# --- FastAPI App & DI ---
app = FastAPI(title="Search & Filtering Microservice (with Cache)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> CatalogClientRepository:
    return CatalogClientRepository()

def get_service(repo: CatalogClientRepository = Depends(get_repo)) -> SearchService:
    return SearchService(repo)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "search-service",
        "cache_backend": "Redis" if cache.redis_client else "In-Memory",
        "version": "2.0.0"
    }

@app.get("/search", response_model=SearchResult)
async def search_products(
    response: Response,
    q: str = Query("", description="Search term for title/desc/tags"),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    tag: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="'price_asc', 'price_desc', 'rating_desc'"),
    service: SearchService = Depends(get_service)
):
    result, is_hit = await service.search(q, category, min_price, max_price, tag, sort_by)
    response.headers["X-Cache"] = "HIT" if is_hit else "MISS"
    response.headers["X-Cache-Backend"] = result.cache_backend
    return result

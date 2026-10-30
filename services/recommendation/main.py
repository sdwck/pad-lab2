import os
import time
from typing import List, Optional
import httpx
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-service:8002")

class RecommendedProduct(BaseModel):
    id: str
    title: str
    category: str
    price: float
    rating: float
    image_url: str
    similarity_score: float
    reason: str

# --- Repository Pattern (Remote Catalog Gateway) ---
class CatalogClient:
    def __init__(self, catalog_url: str = CATALOG_URL):
        self.catalog_url = catalog_url

    async def get_all_products(self) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.catalog_url}/products")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return []

    async def get_product(self, product_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.catalog_url}/products/{product_id}")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return None

# --- Service Layer Pattern ---
class RecommendationService:
    def __init__(self, client: CatalogClient):
        self.client = client

    async def get_recommendations_for_product(self, product_id: str, limit: int = 3) -> List[RecommendedProduct]:
        target = await self.client.get_product(product_id)
        all_prods = await self.client.get_all_products()

        if not target or not all_prods:
            return []

        target_cat = target.get("category", "")
        target_tags = set(target.get("tags", []))

        scores = []
        for p in all_prods:
            if p["id"] == product_id:
                continue

            score = 0.0
            reasons = []

            # Category match gives 0.5
            if p.get("category") == target_cat:
                score += 0.5
                reasons.append(f"Same category ({target_cat})")

            # Tag overlap gives 0.2 per matching tag
            tags = set(p.get("tags", []))
            common = target_tags.intersection(tags)
            if common:
                score += min(0.4, len(common) * 0.2)
                reasons.append(f"Shared tags: {', '.join(common)}")

            # Rating boost
            rating = p.get("rating", 4.5)
            score += (rating / 5.0) * 0.1

            score = round(score, 2)
            scores.append((p, score, " | ".join(reasons) or "Popular in store"))

        scores.sort(key=lambda x: x[1], reverse=True)

        recommendations = []
        for p, score, reason in scores[:limit]:
            recommendations.append(RecommendedProduct(
                id=p["id"],
                title=p["title"],
                category=p["category"],
                price=p["price"],
                rating=p.get("rating", 4.8),
                image_url=p.get("image_url", ""),
                similarity_score=score,
                reason=reason
            ))

        return recommendations

    async def get_trending(self, limit: int = 4) -> List[RecommendedProduct]:
        all_prods = await self.client.get_all_products()
        sorted_prods = sorted(all_prods, key=lambda x: (x.get("rating", 0), x.get("reviews_count", 0)), reverse=True)
        return [
            RecommendedProduct(
                id=p["id"],
                title=p["title"],
                category=p["category"],
                price=p["price"],
                rating=p.get("rating", 5.0),
                image_url=p.get("image_url", ""),
                similarity_score=1.0,
                reason="Top Rated & Best Seller"
            ) for p in sorted_prods[:limit]
        ]

# --- FastAPI App & DI ---
app = FastAPI(title="Smart Recommendation Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_client() -> CatalogClient:
    return CatalogClient()

def get_service(client: CatalogClient = Depends(get_client)) -> RecommendationService:
    return RecommendationService(client)

@app.get("/health")
def health():
    return {"status": "ok", "service": "recommendation-service", "version": "2.0.0"}

@app.get("/recommendations/product/{product_id}", response_model=List[RecommendedProduct])
async def get_product_recommendations(product_id: str, limit: int = 3, service: RecommendationService = Depends(get_service)):
    return await service.get_recommendations_for_product(product_id, limit)

@app.get("/recommendations/trending", response_model=List[RecommendedProduct])
async def get_trending(limit: int = 4, service: RecommendationService = Depends(get_service)):
    return await service.get_trending(limit)

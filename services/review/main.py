import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/reviews.json" if os.path.exists("/data") else "reviews_data.json")

class ReviewCreate(BaseModel):
    product_id: str
    user_id: str
    user_name: str
    rating: int = Field(ge=1, le=5)
    comment: str

class Review(BaseModel):
    id: str
    product_id: str
    user_id: str
    user_name: str
    rating: int
    comment: str
    created_at: float = Field(default_factory=time.time)

class RatingStats(BaseModel):
    product_id: str
    average_rating: float
    total_reviews: int
    distribution: Dict[int, int]

# --- Repository Pattern ---
class ReviewRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            sample_reviews = [
                {
                    "id": "rev_1",
                    "product_id": "prod_1",
                    "user_id": "user_demo",
                    "user_name": "Tima Diaconu",
                    "rating": 5,
                    "comment": "Insane build quality and battery life. Compiles huge Docker containers in seconds.",
                    "created_at": time.time() - 40000
                },
                {
                    "id": "rev_2",
                    "product_id": "prod_3",
                    "user_id": "user_demo",
                    "user_name": "Tima Diaconu",
                    "rating": 5,
                    "comment": "The double gasket typing feel on the Keychron Q1 is next-level.",
                    "created_at": time.time() - 20000
                }
            ]
            self._save({r["id"]: r for r in sample_reviews})

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_by_product(self, product_id: str) -> List[dict]:
        revs = [r for r in self._load().values() if r.get("product_id") == product_id]
        revs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return revs

    def save(self, review: dict):
        revs = self._load()
        revs[review["id"]] = review
        self._save(revs)

# --- Service Layer Pattern ---
class ReviewService:
    def __init__(self, repo: ReviewRepository):
        self.repo = repo

    def add_review(self, dto: ReviewCreate) -> Review:
        rid = f"rev_{int(time.time() * 1000)}"
        record = {
            "id": rid,
            "product_id": dto.product_id,
            "user_id": dto.user_id,
            "user_name": dto.user_name,
            "rating": dto.rating,
            "comment": dto.comment,
            "created_at": time.time()
        }
        self.repo.save(record)
        return Review(**record)

    def get_product_reviews(self, product_id: str) -> List[Review]:
        return [Review(**r) for r in self.repo.get_by_product(product_id)]

    def get_stats(self, product_id: str) -> RatingStats:
        reviews = self.repo.get_by_product(product_id)
        if not reviews:
            return RatingStats(
                product_id=product_id,
                average_rating=5.0,
                total_reviews=0,
                distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            )

        dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total_score = 0
        for r in reviews:
            rt = int(r.get("rating", 5))
            dist[rt] = dist.get(rt, 0) + 1
            total_score += rt

        avg = round(total_score / len(reviews), 2)
        return RatingStats(
            product_id=product_id,
            average_rating=avg,
            total_reviews=len(reviews),
            distribution=dist
        )

# --- FastAPI App & DI ---
app = FastAPI(title="Product Reviews & Ratings Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> ReviewRepository:
    return ReviewRepository()

def get_service(repo: ReviewRepository = Depends(get_repo)) -> ReviewService:
    return ReviewService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "review-service", "version": "2.0.0"}

@app.post("/reviews", response_model=Review)
def create_review(dto: ReviewCreate, service: ReviewService = Depends(get_service)):
    return service.add_review(dto)

@app.get("/reviews/product/{product_id}", response_model=List[Review])
def get_product_reviews(product_id: str, service: ReviewService = Depends(get_service)):
    return service.get_product_reviews(product_id)

@app.get("/reviews/stats/{product_id}", response_model=RatingStats)
def get_rating_stats(product_id: str, service: ReviewService = Depends(get_service)):
    return service.get_stats(product_id)

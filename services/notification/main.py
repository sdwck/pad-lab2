import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/notifications.json" if os.path.exists("/data") else "notifications_data.json")

class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str = "info"  # "info", "order", "payment", "promo"

class Notification(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    type: str
    is_read: bool = False
    created_at: float = Field(default_factory=time.time)

# --- Repository Pattern ---
class NotificationRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            initial = [
                {
                    "id": "notif_welcome",
                    "user_id": "user_demo",
                    "title": "Welcome to PAD Market!",
                    "message": "Welcome to the distributed microservices e-commerce lab platform.",
                    "type": "info",
                    "is_read": True,
                    "created_at": time.time() - 90000
                }
            ]
            self._save({n["id"]: n for n in initial})

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_by_user(self, user_id: str) -> List[dict]:
        notifs = [n for n in self._load().values() if n.get("user_id") == user_id]
        notifs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return notifs

    def get_by_id(self, notif_id: str) -> Optional[dict]:
        return self._load().get(notif_id)

    def save(self, record: dict):
        notifs = self._load()
        notifs[record["id"]] = record
        self._save(notifs)

# --- Service Layer Pattern ---
class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def send_notification(self, dto: NotificationCreate) -> Notification:
        nid = f"notif_{int(time.time() * 1000)}"
        record = {
            "id": nid,
            "user_id": dto.user_id,
            "title": dto.title,
            "message": dto.message,
            "type": dto.type,
            "is_read": False,
            "created_at": time.time()
        }
        self.repo.save(record)
        return Notification(**record)

    def mark_as_read(self, notif_id: str) -> Notification:
        record = self.repo.get_by_id(notif_id)
        if not record:
            raise HTTPException(status_code=404, detail="Notification not found")
        record["is_read"] = True
        self.repo.save(record)
        return Notification(**record)

    def get_user_notifications(self, user_id: str) -> List[Notification]:
        return [Notification(**n) for n in self.repo.get_by_user(user_id)]

# --- FastAPI App & DI ---
app = FastAPI(title="Notification & Events Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> NotificationRepository:
    return NotificationRepository()

def get_service(repo: NotificationRepository = Depends(get_repo)) -> NotificationService:
    return NotificationService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service", "version": "2.0.0"}

@app.post("/notifications/send", response_model=Notification)
def send_notification(dto: NotificationCreate, service: NotificationService = Depends(get_service)):
    return service.send_notification(dto)

@app.get("/recent", response_model=List[Notification])
@app.get("/notifications/recent", response_model=List[Notification])
def get_recent_notifications(limit: int = 30, service: NotificationService = Depends(get_service)):
    all_notifs = list(service.repo._load().values())
    all_notifs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return [Notification(**n) for n in all_notifs[:limit]]

@app.get("/notifications/user/{user_id}", response_model=List[Notification])
def get_user_notifications(user_id: str, service: NotificationService = Depends(get_service)):
    return service.get_user_notifications(user_id)

@app.patch("/notifications/{notification_id}/read", response_model=Notification)
def mark_read(notification_id: str, service: NotificationService = Depends(get_service)):
    return service.mark_as_read(notification_id)

import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/audit.json" if os.path.exists("/data") else "audit_data.json")

class AuditLogCreate(BaseModel):
    service: str
    action: str
    user_id: Optional[str] = "anonymous"
    details: str
    ip_address: Optional[str] = "internal-docker"

class AuditLogEntry(BaseModel):
    id: str
    service: str
    action: str
    user_id: str
    details: str
    ip_address: str
    timestamp: float = Field(default_factory=time.time)

# --- Repository Pattern ---
class AuditRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            sample = [
                {
                    "id": "aud_1",
                    "service": "auth-service",
                    "action": "USER_REGISTER",
                    "user_id": "user_demo",
                    "details": "Registered new student account (student@utm.md)",
                    "ip_address": "127.0.0.1",
                    "timestamp": time.time() - 90000
                },
                {
                    "id": "aud_2",
                    "service": "order-service",
                    "action": "ORDER_CREATED",
                    "user_id": "user_demo",
                    "details": "Order ord_1001 placed for Keychron Q1 Pro",
                    "ip_address": "127.0.0.1",
                    "timestamp": time.time() - 86400
                }
            ]
            self._save({a["id"]: a for a in sample})

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
        entries = list(self._load().values())
        entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return entries

    def save(self, entry: dict):
        logs = self._load()
        logs[entry["id"]] = entry
        self._save(logs)

# --- Service Layer Pattern ---
class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    def record_log(self, dto: AuditLogCreate) -> AuditLogEntry:
        aid = f"aud_{int(time.time() * 1000)}"
        entry = {
            "id": aid,
            "service": dto.service,
            "action": dto.action,
            "user_id": dto.user_id or "anonymous",
            "details": dto.details,
            "ip_address": dto.ip_address or "internal",
            "timestamp": time.time()
        }
        self.repo.save(entry)
        return AuditLogEntry(**entry)

    def list_logs(self, service: Optional[str] = None, user_id: Optional[str] = None, limit: int = 50) -> List[AuditLogEntry]:
        all_logs = self.repo.get_all()
        if service:
            all_logs = [l for l in all_logs if l.get("service") == service]
        if user_id:
            all_logs = [l for l in all_logs if l.get("user_id") == user_id]
        return [AuditLogEntry(**l) for l in all_logs[:limit]]

# --- FastAPI App & DI ---
app = FastAPI(title="Distributed Audit & Security Log Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> AuditRepository:
    return AuditRepository()

def get_service(repo: AuditRepository = Depends(get_repo)) -> AuditService:
    return AuditService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "audit-service", "version": "2.0.0"}

@app.post("/audit/log", response_model=AuditLogEntry)
def log_event(dto: AuditLogCreate, service: AuditService = Depends(get_service)):
    return service.record_log(dto)

@app.get("/audit/logs", response_model=List[AuditLogEntry])
def list_logs(
    service_name: Optional[str] = Query(None, alias="service"),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    service: AuditService = Depends(get_service)
):
    return service.list_logs(service=service_name, user_id=user_id, limit=limit)

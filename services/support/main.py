import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/support.json" if os.path.exists("/data") else "support_data.json")

class TicketMessage(BaseModel):
    id: str
    sender_name: str
    is_staff: bool
    text: str
    timestamp: float = Field(default_factory=time.time)

class TicketCreate(BaseModel):
    user_id: str
    user_name: str
    subject: str
    priority: str = "normal"  # low, normal, urgent
    initial_message: str

class MessageCreate(BaseModel):
    sender_name: str
    is_staff: bool = False
    text: str

class SupportTicket(BaseModel):
    id: str
    user_id: str
    user_name: str
    subject: str
    priority: str
    status: str  # OPEN, RESOLVED, CLOSED
    messages: List[TicketMessage] = []
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

# --- Repository Pattern ---
class SupportTicketRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            sample = {
                "tkt_101": {
                    "id": "tkt_101",
                    "user_id": "user_demo",
                    "user_name": "Tima Diaconu",
                    "subject": "Delivery inquiry for Chișinău area",
                    "priority": "normal",
                    "status": "OPEN",
                    "messages": [
                        {
                            "id": "msg_1",
                            "sender_name": "Tima Diaconu",
                            "is_staff": False,
                            "text": "Hello, how fast is delivery for Raspberry Pi 5 within Rîșcani district?",
                            "timestamp": time.time() - 36000
                        },
                        {
                            "id": "msg_2",
                            "sender_name": "Support Agent Victor",
                            "is_staff": True,
                            "text": "Hi Tima! Orders confirmed before 14:00 arrive same-day via local courier.",
                            "timestamp": time.time() - 30000
                        }
                    ],
                    "created_at": time.time() - 36000,
                    "updated_at": time.time() - 30000
                }
            }
            self._save(sample)

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_by_id(self, ticket_id: str) -> Optional[dict]:
        return self._load().get(ticket_id)

    def get_by_user(self, user_id: str) -> List[dict]:
        tickets = [t for t in self._load().values() if t.get("user_id") == user_id]
        tickets.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return tickets

    def save(self, record: dict):
        tickets = self._load()
        tickets[record["id"]] = record
        self._save(tickets)

# --- Service Layer Pattern ---
class SupportService:
    def __init__(self, repo: SupportTicketRepository):
        self.repo = repo

    def create_ticket(self, dto: TicketCreate) -> SupportTicket:
        tid = f"tkt_{int(time.time() * 1000)}"
        first_msg = {
            "id": f"msg_{int(time.time() * 1000)}",
            "sender_name": dto.user_name,
            "is_staff": False,
            "text": dto.initial_message,
            "timestamp": time.time()
        }
        ticket = {
            "id": tid,
            "user_id": dto.user_id,
            "user_name": dto.user_name,
            "subject": dto.subject,
            "priority": dto.priority,
            "status": "OPEN",
            "messages": [first_msg],
            "created_at": time.time(),
            "updated_at": time.time()
        }
        self.repo.save(ticket)
        return SupportTicket(**ticket)

    def add_message(self, ticket_id: str, dto: MessageCreate) -> SupportTicket:
        tkt = self.repo.get_by_id(ticket_id)
        if not tkt:
            raise HTTPException(status_code=404, detail="Ticket not found")

        msg = {
            "id": f"msg_{int(time.time() * 1000)}",
            "sender_name": dto.sender_name,
            "is_staff": dto.is_staff,
            "text": dto.text,
            "timestamp": time.time()
        }
        tkt["messages"].append(msg)
        tkt["updated_at"] = time.time()
        self.repo.save(tkt)
        return SupportTicket(**tkt)

    def resolve_ticket(self, ticket_id: str) -> SupportTicket:
        tkt = self.repo.get_by_id(ticket_id)
        if not tkt:
            raise HTTPException(status_code=404, detail="Ticket not found")
        tkt["status"] = "RESOLVED"
        tkt["updated_at"] = time.time()
        self.repo.save(tkt)
        return SupportTicket(**tkt)

    def get_ticket(self, ticket_id: str) -> SupportTicket:
        tkt = self.repo.get_by_id(ticket_id)
        if not tkt:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return SupportTicket(**tkt)

    def get_user_tickets(self, user_id: str) -> List[SupportTicket]:
        return [SupportTicket(**t) for t in self.repo.get_by_user(user_id)]

# --- FastAPI App & DI ---
app = FastAPI(title="Customer Support & Tickets Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> SupportTicketRepository:
    return SupportTicketRepository()

def get_service(repo: SupportTicketRepository = Depends(get_repo)) -> SupportService:
    return SupportService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "support-service", "version": "2.0.0"}

@app.post("/tickets", response_model=SupportTicket)
def create_ticket(dto: TicketCreate, service: SupportService = Depends(get_service)):
    return service.create_ticket(dto)

@app.get("/tickets/user/{user_id}", response_model=List[SupportTicket])
def list_user_tickets(user_id: str, service: SupportService = Depends(get_service)):
    return service.get_user_tickets(user_id)

@app.get("/tickets/{ticket_id}", response_model=SupportTicket)
def get_ticket(ticket_id: str, service: SupportService = Depends(get_service)):
    return service.get_ticket(ticket_id)

@app.post("/tickets/{ticket_id}/messages", response_model=SupportTicket)
def reply_to_ticket(ticket_id: str, dto: MessageCreate, service: SupportService = Depends(get_service)):
    return service.add_message(ticket_id, dto)

@app.patch("/tickets/{ticket_id}/resolve", response_model=SupportTicket)
def resolve_ticket(ticket_id: str, service: SupportService = Depends(get_service)):
    return service.resolve_ticket(ticket_id)

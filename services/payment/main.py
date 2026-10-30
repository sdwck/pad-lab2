import json
import os
import time
from typing import Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_FILE = os.getenv("DATA_FILE", "/data/payments.json" if os.path.exists("/data") else "payments_data.json")
ORDER_URL = os.getenv("ORDER_URL", "http://order-service:8005")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification-service:8009")
AUDIT_URL = os.getenv("AUDIT_URL", "http://audit-service:8012")

class PaymentRequest(BaseModel):
    order_id: str
    user_id: str
    amount: float
    card_number: str
    card_holder: str
    exp_month: str
    exp_year: str
    cvv: str

class PaymentTransaction(BaseModel):
    id: str
    order_id: str
    user_id: str
    amount: float
    card_masked: str
    card_holder: str
    status: str  # SUCCESS, FAILED
    error_reason: Optional[str] = None
    created_at: float = Field(default_factory=time.time)

# --- Repository Pattern ---
class PaymentTransactionRepository:
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

    def get_by_id(self, tx_id: str) -> Optional[dict]:
        return self._load().get(tx_id)

    def get_by_order(self, order_id: str) -> Optional[dict]:
        for tx in self._load().values():
            if tx.get("order_id") == order_id:
                return tx
        return None

    def get_all(self) -> List[dict]:
        txs = list(self._load().values())
        txs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return txs

    def save(self, tx: dict):
        txs = self._load()
        txs[tx["id"]] = tx
        self._save(txs)

# --- Service Layer Pattern ---
class PaymentService:
    def __init__(self, repo: PaymentTransactionRepository):
        self.repo = repo

    async def process_payment(self, dto: PaymentRequest) -> PaymentTransaction:
        existing = self.repo.get_by_order(dto.order_id)
        if existing and existing.get("status") == "SUCCESS":
            raise HTTPException(status_code=400, detail="Order has already been paid successfully")

        # Basic Luhn / dummy validation
        clean_card = dto.card_number.replace(" ", "").replace("-", "")
        if len(clean_card) < 13:
            raise HTTPException(status_code=400, detail="Invalid card number format")

        masked = f"**** **** **** {clean_card[-4:]}"
        tx_id = f"tx_{int(time.time() * 1000)}"

        # Simulating payment gateway approval
        status = "SUCCESS"
        error_msg = None
        if clean_card.endswith("0000"):
            status = "FAILED"
            error_msg = "Card declined: insufficient funds (test simulation)"

        tx_record = {
            "id": tx_id,
            "order_id": dto.order_id,
            "user_id": dto.user_id,
            "amount": dto.amount,
            "card_masked": masked,
            "card_holder": dto.card_holder.upper(),
            "status": status,
            "error_reason": error_msg,
            "created_at": time.time()
        }

        self.repo.save(tx_record)

        if status == "SUCCESS":
            # Update order status in order-service
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    await client.patch(f"{ORDER_URL}/orders/{dto.order_id}/status", json={"status": "PAID"})
                    await client.post(f"{NOTIFICATION_URL}/notifications/send", json={
                        "user_id": dto.user_id,
                        "title": "Payment Confirmed",
                        "message": f"Payment of ${dto.amount} for Order #{dto.order_id} was successful. Tx: {tx_id}",
                        "type": "payment"
                    })
                    await client.post(f"{AUDIT_URL}/audit/log", json={
                        "service": "payment-service",
                        "action": "PAYMENT_PROCESSED",
                        "user_id": dto.user_id,
                        "details": f"Tx {tx_id}: ${dto.amount} charged successfully on order {dto.order_id}"
                    })
            except Exception:
                pass
        else:
            raise HTTPException(status_code=402, detail=error_msg)

        return PaymentTransaction(**tx_record)

    def get_transaction(self, tx_id: str) -> PaymentTransaction:
        tx = self.repo.get_by_id(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return PaymentTransaction(**tx)

    def get_by_order(self, order_id: str) -> Optional[PaymentTransaction]:
        tx = self.repo.get_by_order(order_id)
        return PaymentTransaction(**tx) if tx else None

    def list_all(self) -> List[PaymentTransaction]:
        return [PaymentTransaction(**t) for t in self.repo.get_all()]

# --- FastAPI App & DI ---
app = FastAPI(title="Payment Gateway Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repo() -> PaymentTransactionRepository:
    return PaymentTransactionRepository()

def get_service(repo: PaymentTransactionRepository = Depends(get_repo)) -> PaymentService:
    return PaymentService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service", "version": "2.0.0"}

@app.post("/payments/process", response_model=PaymentTransaction)
async def process_payment(dto: PaymentRequest, service: PaymentService = Depends(get_service)):
    return await service.process_payment(dto)

@app.get("/payments/order/{order_id}", response_model=Optional[PaymentTransaction])
def get_order_payment(order_id: str, service: PaymentService = Depends(get_service)):
    return service.get_by_order(order_id)

@app.get("/payments/{tx_id}", response_model=PaymentTransaction)
def get_transaction(tx_id: str, service: PaymentService = Depends(get_service)):
    return service.get_transaction(tx_id)

@app.get("/payments", response_model=List[PaymentTransaction])
def list_transactions(service: PaymentService = Depends(get_service)):
    return service.list_all()

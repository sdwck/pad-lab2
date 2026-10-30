import hashlib
import hmac
import json
import os
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-pad-lab2-utm")
DATA_FILE = os.getenv("DATA_FILE", "/data/auth.json" if os.path.exists("/data") else "auth_data.json")

# --- Domain Models ---
class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    role: str = "user"  # "user" or "admin"

class UserLogin(BaseModel):
    email: str
    password: str

class UserPublic(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: str
    created_at: float

class TokenResponse(BaseModel):
    token: str
    user: UserPublic

# --- Security Helpers (Lightweight JWT) ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: str, email: str, role: str) -> str:
    header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    payload_data = json.dumps({
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + 86400 * 7
    })
    import base64
    payload = base64.urlsafe_b64encode(payload_data.encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"{header}.{payload}.{signature}"

def decode_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token structure")
    header, payload, sig = parts
    expected_sig = hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")
    import base64
    padded = payload + "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded).decode())
    if data.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")
    return data

# --- Repository Pattern ---
class UserRepository:
    def __init__(self, file_path: str = DATA_FILE):
        self.file_path = file_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.file_path):
            # Seed default admin and customer demo accounts
            admin_id = "user_admin"
            user_id = "user_demo"
            initial_data = {
                admin_id: {
                    "id": admin_id,
                    "username": "admin",
                    "email": "admin@cloudmart.io",
                    "password_hash": hash_password("admin123"),
                    "full_name": "Alex Mercer",
                    "role": "admin",
                    "created_at": time.time()
                },
                user_id: {
                    "id": user_id,
                    "username": "david",
                    "email": "customer@cloudmart.io",
                    "password_hash": hash_password("customer123"),
                    "full_name": "David Chen",
                    "role": "user",
                    "created_at": time.time()
                },
                "user_legacy": {
                    "id": "user_legacy",
                    "username": "student",
                    "email": "student@utm.md",
                    "password_hash": hash_password("student123"),
                    "full_name": "David Chen",
                    "role": "user",
                    "created_at": time.time()
                }
            }
            self._save(initial_data)

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, dict]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_by_id(self, user_id: str) -> Optional[dict]:
        return self._load().get(user_id)

    def get_by_email(self, email: str) -> Optional[dict]:
        for u in self._load().values():
            if u["email"].lower() == email.lower():
                return u
        return None

    def get_all(self) -> List[dict]:
        return list(self._load().values())

    def save_user(self, user_data: dict):
        users = self._load()
        users[user_data["id"]] = user_data
        self._save(users)

# --- Service Layer Pattern ---
class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register(self, dto: UserRegister) -> TokenResponse:
        if self.repo.get_by_email(dto.email):
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        user_id = f"user_{int(time.time() * 1000)}"
        user_record = {
            "id": user_id,
            "username": dto.username,
            "email": dto.email.lower(),
            "password_hash": hash_password(dto.password),
            "full_name": dto.full_name,
            "role": dto.role if dto.role in ["user", "admin"] else "user",
            "created_at": time.time()
        }
        self.repo.save_user(user_record)
        token = create_token(user_id, user_record["email"], user_record["role"])
        return TokenResponse(
            token=token,
            user=UserPublic(**{k: v for k, v in user_record.items() if k != "password_hash"})
        )

    def login(self, dto: UserLogin) -> TokenResponse:
        user = self.repo.get_by_email(dto.email)
        if not user or user["password_hash"] != hash_password(dto.password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        token = create_token(user["id"], user["email"], user["role"])
        return TokenResponse(
            token=token,
            user=UserPublic(**{k: v for k, v in user.items() if k != "password_hash"})
        )

    def get_current_user(self, token: str) -> UserPublic:
        payload = decode_token(token)
        user = self.repo.get_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserPublic(**{k: v for k, v in user.items() if k != "password_hash"})

# --- FastAPI App & Dependency Injection ---
app = FastAPI(title="Auth & Identity Microservice", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_repository() -> UserRepository:
    return UserRepository()

def get_service(repo: UserRepository = Depends(get_repository)) -> AuthService:
    return AuthService(repo)

@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service", "version": "2.0.0"}

@app.post("/register", response_model=TokenResponse)
def register(dto: UserRegister, service: AuthService = Depends(get_service)):
    return service.register(dto)

@app.post("/login", response_model=TokenResponse)
def login(dto: UserLogin, service: AuthService = Depends(get_service)):
    return service.login(dto)

@app.get("/me", response_model=UserPublic)
def get_me(authorization: Optional[str] = Header(None), service: AuthService = Depends(get_service)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ")[1]
    return service.get_current_user(token)

@app.get("/users", response_model=List[UserPublic])
def list_users(repo: UserRepository = Depends(get_repository)):
    users = repo.get_all()
    return [UserPublic(**{k: v for k, v in u.items() if k != "password_hash"}) for u in users]

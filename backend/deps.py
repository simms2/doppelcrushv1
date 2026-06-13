"""Shared dependencies for the DoppelCrush API.

Singletons (db client, vector store, ranker) plus reusable helpers
(JWT auth, password hashing, rate limiting) live here so the routers
can stay thin and free of glue code.
"""
from __future__ import annotations

import logging
import os
import secrets
import string
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from matching import MODEL_FACEAPI, MongoVectorStore, Ranker  # noqa: E402

logger = logging.getLogger("doppelcrush")

# ── Config & DB singletons ─────────────────────────────────────────────────
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_TTL_DAYS = 30

mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]

vector_store = MongoVectorStore(db)


async def _bulk_load_users(user_ids: Iterable[str]) -> dict[str, dict]:
    if not user_ids:
        return {}
    docs = await db.users.find(
        {"id": {"$in": list(user_ids)}}, {"_id": 0, "password_hash": 0}
    ).to_list(500)
    return {d["id"]: d for d in docs}


ranker = Ranker(vector_store, _bulk_load_users)


# ── Time / id helpers ──────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Auth helpers ───────────────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_TTL_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def generate_referral_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Helpers shared across routers ──────────────────────────────────────────
def public_profile(doc: dict) -> dict:
    """Strip sensitive fields from a profile document."""
    return {
        "id": doc["id"],
        "name": doc.get("name"),
        "age": doc.get("age"),
        "gender": doc.get("gender"),
        "bio": doc.get("bio"),
        "photo_url": doc.get("photo_url"),
        "location": doc.get("location"),
        "is_seed": doc.get("is_seed", False),
    }


async def match_or_403(match_id: str, user_id: str) -> dict:
    match = await db.matches.find_one({"id": match_id, "users": user_id}, {"_id": 0})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


# ── Tiny in-process sliding-window rate limiter ────────────────────────────
_rate_buckets: dict[str, deque] = {}


def rate_limit(key: str, max_calls: int, window_sec: float) -> bool:
    """Returns True if the call is allowed, False if rate-limited.

    Resolution: per-process. For multi-replica deployments wire to Redis,
    same interface."""
    now = time.time()
    bucket = _rate_buckets.setdefault(key, deque())
    cutoff = now - window_sec
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    return True


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "unknown") or "unknown"


# Re-exported for callers
__all__ = [
    "JWT_SECRET",
    "JWT_ALG",
    "db",
    "mongo_client",
    "vector_store",
    "ranker",
    "now_iso",
    "hash_password",
    "verify_password",
    "create_access_token",
    "generate_referral_code",
    "get_current_user",
    "public_profile",
    "match_or_403",
    "rate_limit",
    "client_ip",
    "MODEL_FACEAPI",
]

"""DoppelCrush backend - FastAPI server."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging
import math
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

from seed_data import get_seed_profiles_with_embeddings
from storage import APP_NAME, get_object, init_storage, put_object
from moderation import check_selfie
from matching import (
    MODEL_FACEAPI,
    MODEL_SYNTHETIC,
    MongoVectorStore,
    Ranker,
    chaos_score,
    twin_energy_score,
)

# ---------------------------------------------------------------------------
# Config & DB
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_TTL_DAYS = 30

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Matching subsystem (swap MongoVectorStore for pgvector/Qdrant at scale).
vector_store = MongoVectorStore(db)


async def _bulk_load_users(user_ids):
    if not user_ids:
        return {}
    docs = await db.users.find({"id": {"$in": list(user_ids)}}, {"_id": 0, "password_hash": 0}).to_list(500)
    return {d["id"]: d for d in docs}


ranker = Ranker(vector_store, _bulk_load_users)

app = FastAPI(title="DoppelCrush API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doppelcrush")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
Gender = Literal["woman", "man", "nonbinary"]
LookingFor = Literal["women", "men", "everyone"]
Mode = Literal["doppel", "chaos"]


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=40)
    ref: Optional[str] = None
    twin_id: Optional[str] = None  # if set, auto-create compare room with that user
    source: Optional[str] = None   # "twin", "share_card", "invite", etc — analytics


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class OnboardingIn(BaseModel):
    age: int = Field(ge=18, le=120)
    gender: Gender
    looking_for: LookingFor
    mode: Mode
    bio: Optional[str] = ""
    location: Optional[str] = ""
    photo_url: Optional[str] = None
    embedding: List[float] = Field(default_factory=list)
    quality_score: Optional[float] = Field(default=0.6, ge=0.0, le=1.0)
    model_version: Optional[str] = MODEL_FACEAPI


class SwipeIn(BaseModel):
    target_id: str
    direction: Literal["like", "pass"]


class ShareEventIn(BaseModel):
    kind: Literal["reveal_card", "invite", "match_card", "story", "square"]
    target_id: Optional[str] = None


class CompareCreateIn(BaseModel):
    title: Optional[str] = "DoppelCrush group challenge"


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Routes - meta
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"ok": True, "service": "DoppelCrush"}


# ---------------------------------------------------------------------------
# Routes - auth
# ---------------------------------------------------------------------------
@api.post("/auth/signup")
async def signup(data: SignupIn):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "name": data.name,
        "password_hash": hash_password(data.password),
        "referral_code": generate_referral_code(),
        "referred_by": data.ref,
        "onboarding_complete": False,
        "mode": "doppel",
        "extra_daily_matches": 0,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    # referral credit
    if data.ref:
        await db.users.update_one(
            {"referral_code": data.ref},
            {"$inc": {"extra_daily_matches": 3}},
        )
        await db.referrals.insert_one(
            {
                "id": str(uuid.uuid4()),
                "code": data.ref,
                "new_user_id": user_id,
                "source": data.source,
                "twin_id": data.twin_id,
                "created_at": now_iso(),
            }
        )
    # Twin share: create a 1:1 compare room linking inviter ↔ new user
    if data.twin_id:
        twin = await db.users.find_one({"id": data.twin_id}, {"_id": 0})
        if twin:
            room_id = str(uuid.uuid4())[:8]
            await db.compare_rooms.insert_one({
                "id": room_id,
                "host_id": twin["id"],
                "title": f"You vs {twin.get('name','your twin')}",
                "participants": [twin["id"], user_id],
                "source": "twin_share",
                "created_at": now_iso(),
            })
    token = create_access_token(user_id)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return {"token": token, "user": doc}


@api.post("/auth/login")
async def login(data: LoginIn):
    email = data.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"])
    user.pop("password_hash", None)
    return {"token": token, "user": user}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    user.pop("password_hash", None)
    user.pop("embedding", None)
    return user


# ---------------------------------------------------------------------------
# Routes - onboarding & profile
# ---------------------------------------------------------------------------
@api.post("/onboarding")
async def complete_onboarding(
    data: OnboardingIn, user: dict = Depends(get_current_user)
):
    updates = {
        "age": data.age,
        "gender": data.gender,
        "looking_for": data.looking_for,
        "mode": data.mode,
        "bio": data.bio or "",
        "location": data.location or "",
        "photo_url": data.photo_url,
        "embedding": data.embedding,
        "embedding_quality": data.quality_score,
        "embedding_model": data.model_version,
        "onboarding_complete": True,
        "moderation_state": "ok",
        "onboarded_at": now_iso(),
    }
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    if data.embedding:
        await vector_store.upsert(
            user["id"],
            data.embedding,
            {
                "model_version": data.model_version or MODEL_FACEAPI,
                "quality_score": data.quality_score or 0.6,
                "face_detected": True,
            },
        )
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    refreshed.pop("password_hash", None)
    refreshed.pop("embedding", None)
    return refreshed


@api.patch("/me/mode")
async def update_mode(
    body: dict, user: dict = Depends(get_current_user)
):
    mode = body.get("mode")
    if mode not in ("doppel", "chaos"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    await db.users.update_one({"id": user["id"]}, {"$set": {"mode": mode}})
    return {"mode": mode}


# ---------------------------------------------------------------------------
# Routes - discover / matching
# ---------------------------------------------------------------------------
def _gender_filter(looking_for: str) -> Optional[List[str]]:
    if looking_for == "women":
        return ["woman"]
    if looking_for == "men":
        return ["man"]
    return None  # everyone


@api.get("/discover")
async def discover(
    mode: Optional[str] = None,
    limit: int = 12,
    user: dict = Depends(get_current_user),
):
    """Two-stage ranking: ANN retrieval ➜ product rerank.

    Returns Doppel (high similarity, quality-weighted) or Chaos (controlled
    contrast band) candidates. See backend/matching.py for the algorithm.
    """
    active_mode = mode or user.get("mode", "doppel")
    user_embedding = user.get("embedding") or []
    if not user_embedding:
        return {"mode": active_mode, "results": []}
    swiped_ids = {
        s["target_id"]
        async for s in db.swipes.find({"user_id": user["id"]}, {"target_id": 1})
    }
    ranked = await ranker.rank(
        user,
        user_embedding,
        mode=active_mode,
        k=limit,
        retrieval_k=400,
        swiped_ids=swiped_ids,
    )
    results = []
    for r in ranked:
        p = r["profile"]
        if not p.get("photo_url"):
            continue
        results.append(
            {
                **public_profile(p),
                "score": r["score"],
                "mode": active_mode,
                "quality": r["quality"],
                "explanation": r["explanation"],
            }
        )
    return {"mode": active_mode, "results": results}


@api.post("/swipe")
async def swipe(data: SwipeIn, user: dict = Depends(get_current_user)):
    target = await db.users.find_one({"id": data.target_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    await db.swipes.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "target_id": data.target_id,
            "direction": data.direction,
            "created_at": now_iso(),
        }
    )
    is_match = False
    match_id = None
    if data.direction == "like":
        # if target is a seed profile, auto-match for the demo experience
        reciprocal = None
        if target.get("is_seed"):
            is_match = True
        else:
            reciprocal = await db.swipes.find_one(
                {
                    "user_id": data.target_id,
                    "target_id": user["id"],
                    "direction": "like",
                }
            )
            is_match = bool(reciprocal)
        if is_match:
            existing = await db.matches.find_one(
                {"users": {"$all": [user["id"], data.target_id]}},
                {"_id": 0},
            )
            if existing:
                match_id = existing["id"]
            else:
                match_id = str(uuid.uuid4())
                await db.matches.insert_one(
                    {
                        "id": match_id,
                        "users": [user["id"], data.target_id],
                        "created_at": now_iso(),
                    }
                )
    return {"match": is_match, "match_id": match_id, "target": public_profile(target)}


@api.get("/matches")
async def list_matches(user: dict = Depends(get_current_user)):
    docs = await db.matches.find({"users": user["id"]}, {"_id": 0}).to_list(200)
    out = []
    for d in docs:
        other_id = next((u for u in d["users"] if u != user["id"]), None)
        if not other_id:
            continue
        other = await db.users.find_one({"id": other_id}, {"_id": 0})
        if not other:
            continue
        out.append(
            {
                "id": d["id"],
                "created_at": d["created_at"],
                "profile": public_profile(other),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Routes - share / referral
# ---------------------------------------------------------------------------
@api.post("/share")
async def log_share(data: ShareEventIn, user: dict = Depends(get_current_user)):
    await db.share_events.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": data.kind,
            "target_id": data.target_id,
            "created_at": now_iso(),
        }
    )
    # reward
    await db.users.update_one({"id": user["id"]}, {"$inc": {"extra_daily_matches": 1}})
    return {"ok": True}


@api.get("/matches/{match_id}/openers")
async def get_openers(match_id: str, user: dict = Depends(get_current_user)):
    """Return 3 mode-appropriate one-tap starter messages for an existing match."""
    match = await _match_or_403(match_id, user["id"])
    other_id = next((u for u in match["users"] if u != user["id"]), None)
    other = await db.users.find_one({"id": other_id}, {"_id": 0}) if other_id else None
    name = other.get("name") if other else "you"
    mode = user.get("mode", "doppel")
    doppel_openers = [
        f"Twin energy 🪞 — were we separated at birth, {name}?",
        f"ok {name}, your face card is unfair. coffee?",
        "we look way too alike. mildly suspicious.",
        f"{name} — same vibe, same brows, what's the deal?",
    ]
    chaos_openers = [
        "plot twist energy. I'm into it.",
        f"total opposite of my usual type. risky move, {name}?",
        "we make zero sense. let's collide ⚡",
        f"chaos draft pick, {name}. don't disappoint.",
    ]
    pool = doppel_openers if mode == "doppel" else chaos_openers
    return {"openers": pool[:3], "match_id": match_id, "mode": mode}


@api.post("/matches/{match_id}/typing")
async def post_typing(match_id: str, user: dict = Depends(get_current_user)):
    await _match_or_403(match_id, user["id"])
    await db.typing.update_one(
        {"match_id": match_id, "user_id": user["id"]},
        {"$set": {"updated_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True}


@api.get("/matches/{match_id}/state")
async def match_state(match_id: str, user: dict = Depends(get_current_user)):
    """Polled by chat clients — returns whether the other user is typing + unread count."""
    match = await _match_or_403(match_id, user["id"])
    other_id = next((u for u in match["users"] if u != user["id"]), None)
    typing = False
    if other_id:
        t = await db.typing.find_one({"match_id": match_id, "user_id": other_id})
        if t:
            from datetime import datetime as _dt
            updated = _dt.fromisoformat(t["updated_at"])
            if (datetime.now(timezone.utc) - updated).total_seconds() < 5:
                typing = True
    last_read_other = await db.messages.find_one(
        {"match_id": match_id, "sender_id": user["id"], "read": True},
        sort=[("created_at", -1)],
        projection={"_id": 0, "id": 1, "created_at": 1},
    )
    unread = await db.messages.count_documents(
        {"match_id": match_id, "sender_id": {"$ne": user["id"]}, "read": False}
    )
    return {
        "typing": typing,
        "last_read_other_message_id": last_read_other["id"] if last_read_other else None,
        "unread": unread,
    }


@api.get("/me/unread")
async def my_unread(user: dict = Depends(get_current_user)):
    """Total unread across all my matches — used for the nav badge."""
    pipeline = [
        {"$match": {"sender_id": {"$ne": user["id"]}, "read": False}},
        {"$lookup": {"from": "matches", "localField": "match_id", "foreignField": "id", "as": "m"}},
        {"$match": {"m.users": user["id"]}},
        {"$count": "n"},
    ]
    result = await db.messages.aggregate(pipeline).to_list(1)
    n = result[0]["n"] if result else 0
    return {"unread": n}


# ---------------------------------------------------------------------------
# Routes - profile edit
# ---------------------------------------------------------------------------
class ProfilePatch(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    mode: Optional[Literal["doppel", "chaos"]] = None
    looking_for: Optional[Literal["women", "men", "everyone"]] = None
    photo_url: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    embedding_model: Optional[str] = None


@api.patch("/me")
async def patch_me(data: ProfilePatch, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not updates:
        return user
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    # re-upsert the embedding if it was changed
    if "embedding" in updates and isinstance(updates["embedding"], list) and len(updates["embedding"]) >= 64:
        await vector_store.upsert(
            user["id"],
            updates["embedding"],
            {
                "model_version": updates.get("embedding_model") or user.get("embedding_model") or MODEL_FACEAPI,
                "quality_score": updates.get("embedding_quality", user.get("embedding_quality", 0.6)),
                "face_detected": True,
            },
        )
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    refreshed.pop("password_hash", None)
    refreshed.pop("embedding", None)
    return refreshed


@api.delete("/me")
async def delete_me(user: dict = Depends(get_current_user)):
    """Privacy: remove user, their face embedding, swipes, messages, files."""
    uid = user["id"]
    # collect their match ids first so we can wipe orphaned messages too
    match_ids = [m["id"] async for m in db.matches.find({"users": uid}, {"id": 1})]
    await vector_store.delete(uid)
    await db.users.delete_one({"id": uid})
    await db.swipes.delete_many({"$or": [{"user_id": uid}, {"target_id": uid}]})
    await db.matches.delete_many({"users": uid})
    if match_ids:
        await db.messages.delete_many({"match_id": {"$in": match_ids}})
    await db.messages.delete_many({"sender_id": uid})
    await db.files.update_many({"user_id": uid}, {"$set": {"is_deleted": True}})
    await db.share_events.delete_many({"user_id": uid})
    return {"ok": True}


@api.get("/referral/{code}")
async def referral_info(code: str):
    user = await db.users.find_one({"referral_code": code}, {"_id": 0})
    if not user:
        return {"valid": False}
    return {
        "valid": True,
        "name": user.get("name"),
        "photo_url": user.get("photo_url"),
    }


# ---------------------------------------------------------------------------
# Routes - shareable twin page (PUBLIC, no auth)
# ---------------------------------------------------------------------------
@api.get("/share/twin/{user_id}")
async def twin_teaser(user_id: str):
    """Public teaser used by the /your-twin/:user_id viral landing page.

    Returns the minimum information needed to render the share landing:
    name, age band, location, photo_url and the inviter's referral_code so
    the CTA pre-fills the signup form correctly.
    """
    u = await db.users.find_one(
        {"id": user_id, "onboarding_complete": True, "moderation_state": {"$ne": "blocked"}},
        {"_id": 0, "password_hash": 0, "embedding": 0, "email": 0},
    )
    if not u or not u.get("photo_url"):
        return {"valid": False}
    age = u.get("age") or 0
    age_band = f"{(age // 5) * 5}s" if age else None
    return {
        "valid": True,
        "user": {
            "id": u["id"],
            "name": u.get("name"),
            "age_band": age_band,
            "location": u.get("location"),
            "photo_url": u.get("photo_url"),
            "mode": u.get("mode", "doppel"),
            "bio": u.get("bio"),
        },
        "referral_code": u.get("referral_code"),
    }


@api.get("/me/compare-rooms")
async def my_compare_rooms(user: dict = Depends(get_current_user)):
    rooms = await db.compare_rooms.find(
        {"participants": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    out = []
    for r in rooms:
        out.append({
            "id": r["id"],
            "title": r.get("title"),
            "participant_count": len(r.get("participants", [])),
            "source": r.get("source"),
            "created_at": r["created_at"],
        })
    return out


# ---------------------------------------------------------------------------
# Routes - selfie upload (object storage)
# ---------------------------------------------------------------------------
@api.post("/upload/selfie")
async def upload_selfie(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    ext = (file.filename or "selfie.jpg").rsplit(".", 1)[-1].lower()
    if ext not in MIME_BY_EXT:
        raise HTTPException(status_code=400, detail="Only JPG/PNG/WebP allowed")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Selfie too large (max 8MB)")
    # Moderation pass (heuristic stub — swap for real NSFW model in prod)
    verdict = check_selfie(data)
    if not verdict["safe"]:
        raise HTTPException(
            status_code=400,
            detail=f"Selfie flagged by moderation ({verdict.get('reason','flagged')}). Please upload a face-only photo.",
        )
    path = f"{APP_NAME}/selfies/{user['id']}/{uuid.uuid4()}.{ext}"
    content_type = file.content_type or MIME_BY_EXT[ext]
    try:
        result = put_object(path, data, content_type)
    except Exception as e:  # noqa: BLE001
        logger.exception("Storage put failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    await db.files.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "storage_path": result["path"],
            "content_type": content_type,
            "size": result.get("size", len(data)),
            "is_deleted": False,
            "created_at": now_iso(),
        }
    )
    backend = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
    file_path = result["path"]
    return {
        "path": file_path,
        # Frontend can use the absolute URL directly as <img src>
        "url": f"{backend}/api/files/{file_path}" if backend else f"/api/files/{file_path}",
    }


@api.get("/files/{path:path}")
async def serve_file(path: str):
    record = await db.files.find_one(
        {"storage_path": path, "is_deleted": False}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, ctype = get_object(path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Storage read failed: {e}")
    return Response(
        content=data,
        media_type=record.get("content_type", ctype),
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------------------------------------------------------------------------
# Routes - chat between matched users
# ---------------------------------------------------------------------------
async def _match_or_403(match_id: str, user_id: str) -> dict:
    match = await db.matches.find_one({"id": match_id, "users": user_id}, {"_id": 0})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@api.get("/matches/{match_id}")
async def get_match(match_id: str, user: dict = Depends(get_current_user)):
    match = await _match_or_403(match_id, user["id"])
    other_id = next((u for u in match["users"] if u != user["id"]), None)
    other = await db.users.find_one({"id": other_id}, {"_id": 0}) if other_id else None
    return {
        "id": match["id"],
        "created_at": match["created_at"],
        "profile": public_profile(other) if other else None,
    }


@api.get("/matches/{match_id}/messages")
async def list_messages(
    match_id: str,
    since: Optional[datetime] = Query(None),
    user: dict = Depends(get_current_user),
):
    await _match_or_403(match_id, user["id"])
    query: dict = {"match_id": match_id}
    if since:
        query["created_at"] = {"$gt": since.isoformat()}
    msgs = (
        await db.messages.find(query, {"_id": 0})
        .sort("created_at", 1)
        .to_list(500)
    )
    # mark inbound as read
    await db.messages.update_many(
        {"match_id": match_id, "sender_id": {"$ne": user["id"]}, "read": False},
        {"$set": {"read": True}},
    )
    return msgs


@api.post("/matches/{match_id}/messages")
async def send_message(
    match_id: str,
    data: MessageIn,
    user: dict = Depends(get_current_user),
):
    match = await _match_or_403(match_id, user["id"])
    msg = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "sender_id": user["id"],
        "body": data.body.strip(),
        "created_at": now_iso(),
        "read": False,
    }
    await db.messages.insert_one(msg)
    # Auto-reply from seed profile (because they can't log in) for demo feel.
    other_id = next((u for u in match["users"] if u != user["id"]), None)
    if other_id:
        other = await db.users.find_one({"id": other_id}, {"_id": 0})
        if other and other.get("is_seed"):
            replies = [
                f"omg {user.get('name', 'you')}, hi 👋",
                "wait — do we actually look alike?",
                "ok, you're cute. continue.",
                "send a selfie selfie. for science.",
                "what's your chaos mode pick rn?",
                "I'm into it ✨",
            ]
            import random
            reply_body = random.choice(replies)
            await db.messages.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "match_id": match_id,
                    "sender_id": other_id,
                    "body": reply_body,
                    "created_at": now_iso(),
                    "read": False,
                    "auto": True,
                }
            )
    msg.pop("_id", None)
    return msg


# ---------------------------------------------------------------------------
# Routes - growth stats
# ---------------------------------------------------------------------------
@api.get("/me/stats")
async def my_stats(user: dict = Depends(get_current_user)):
    friends_joined = await db.referrals.count_documents({"code": user.get("referral_code")})
    shares = await db.share_events.count_documents({"user_id": user["id"]})
    matches = await db.matches.count_documents({"users": user["id"]})
    return {
        "friends_joined": friends_joined,
        "bonus_matches": user.get("extra_daily_matches", 0),
        "shares": shares,
        "matches": matches,
        "referral_code": user.get("referral_code"),
    }


# ---------------------------------------------------------------------------
# Routes - Compare rooms (group challenge)
# ---------------------------------------------------------------------------
@api.post("/compare")
async def create_compare(data: CompareCreateIn, user: dict = Depends(get_current_user)):
    room_id = str(uuid.uuid4())[:8]
    await db.compare_rooms.insert_one({
        "id": room_id,
        "host_id": user["id"],
        "title": data.title,
        "participants": [user["id"]],
        "created_at": now_iso(),
    })
    return {"id": room_id}


@api.post("/compare/{room_id}/join")
async def join_compare(room_id: str, user: dict = Depends(get_current_user)):
    room = await db.compare_rooms.find_one({"id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user["id"] not in room["participants"]:
        await db.compare_rooms.update_one(
            {"id": room_id},
            {"$addToSet": {"participants": user["id"]}},
        )
    return {"id": room_id, "joined": True}


@api.get("/compare/{room_id}")
async def get_compare(room_id: str, user: dict = Depends(get_current_user)):
    room = await db.compare_rooms.find_one({"id": room_id}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    # auto-join the viewer (low friction)
    if user["id"] not in room["participants"]:
        await db.compare_rooms.update_one(
            {"id": room_id},
            {"$addToSet": {"participants": user["id"]}},
        )
        room["participants"].append(user["id"])

    users = await db.users.find(
        {"id": {"$in": room["participants"]}}, {"_id": 0}
    ).to_list(50)
    # build pairwise similarities
    pairs = []
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            a, b = users[i], users[j]
            if not a.get("embedding") or not b.get("embedding"):
                continue
            sim = cosine_similarity(a["embedding"], b["embedding"])
            pct = max(0, min(100, int(round((sim + 1) * 50))))
            pairs.append({"a": public_profile(a), "b": public_profile(b), "score": pct})
    pairs.sort(key=lambda p: p["score"], reverse=True)
    strongest_twin = pairs[0] if pairs else None
    chaos_contrast = pairs[-1] if len(pairs) > 1 else None
    # funniest = the pair closest to the median score (most "average / unexpected")
    funniest = pairs[len(pairs) // 2] if len(pairs) >= 2 else None
    return {
        "id": room["id"],
        "title": room["title"],
        "participants": [public_profile(u) for u in users if u.get("photo_url")],
        "participant_count": len(room["participants"]),
        "strongest_twin": strongest_twin,
        "funniest_mismatch": funniest,
        "chaos_contrast": chaos_contrast,
        "pairs": pairs,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("referral_code", unique=True, sparse=True)
    await db.swipes.create_index([("user_id", 1), ("target_id", 1)])
    await db.matches.create_index("users")
    await db.messages.create_index([("match_id", 1), ("created_at", 1)])
    await db.files.create_index("storage_path")
    await db.face_embeddings.create_index("user_id", unique=True)


async def seed_profiles():
    """Insert seed/demo profiles if missing AND populate face_embeddings."""
    seeds = get_seed_profiles_with_embeddings()
    for s in seeds:
        existing = await db.users.find_one({"email": f"{s['username']}@seed.doppelcrush"})
        if existing:
            # ensure their embedding exists in the vector store
            await vector_store.upsert(
                existing["id"],
                s["embedding"],
                {"model_version": MODEL_SYNTHETIC, "quality_score": 0.7, "face_detected": True},
            )
            continue
        uid = str(uuid.uuid4())
        await db.users.insert_one(
            {
                "id": uid,
                "email": f"{s['username']}@seed.doppelcrush",
                "name": s["name"],
                "age": s["age"],
                "gender": s["gender"],
                "bio": s["bio"],
                "photo_url": s["photo_url"],
                "location": s["location"],
                "embedding": s["embedding"],
                "embedding_model": MODEL_SYNTHETIC,
                "embedding_quality": 0.7,
                "looking_for": "everyone",
                "mode": "doppel",
                "onboarding_complete": True,
                "moderation_state": "ok",
                "is_seed": True,
                "password_hash": hash_password(secrets.token_hex(16)),
                "referral_code": generate_referral_code(),
                "created_at": now_iso(),
            }
        )
        await vector_store.upsert(
            uid,
            s["embedding"],
            {"model_version": MODEL_SYNTHETIC, "quality_score": 0.7, "face_detected": True},
        )
    logger.info("Seed profiles + embeddings ensured.")


@app.on_event("startup")
async def on_start():
    await ensure_indexes()
    await seed_profiles()
    try:
        init_storage()
    except Exception as e:  # noqa: BLE001
        logger.warning("Storage init deferred: %s", e)


@app.on_event("shutdown")
async def on_stop():
    client.close()


app.include_router(api)


# ---------------------------------------------------------------------------
# WebSocket — optional real-time upgrade for chat (polling remains fallback)
# ---------------------------------------------------------------------------
_ws_rooms: dict[str, set[WebSocket]] = {}


async def _ws_authenticate(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    return await db.users.find_one({"id": payload["sub"]}, {"_id": 0})


@app.websocket("/api/ws/chat/{match_id}")
async def ws_chat(websocket: WebSocket, match_id: str, token: str = Query("")):
    user = await _ws_authenticate(token)
    if not user:
        await websocket.close(code=4401)
        return
    match = await db.matches.find_one({"id": match_id, "users": user["id"]}, {"_id": 0})
    if not match:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    room = _ws_rooms.setdefault(match_id, set())
    room.add(websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            t = payload.get("type")
            if t == "message":
                body = (payload.get("body") or "").strip()
                if not body:
                    continue
                msg = {
                    "id": str(uuid.uuid4()),
                    "match_id": match_id,
                    "sender_id": user["id"],
                    "body": body[:1000],
                    "created_at": now_iso(),
                    "read": False,
                }
                await db.messages.insert_one(msg)
                for peer in list(room):
                    try:
                        await peer.send_json({"type": "message", "message": {**msg, "_id": None}})
                    except Exception:
                        room.discard(peer)
                # Auto-reply from seed profile for demo feel (parity with HTTP path).
                other_id = next((u for u in match["users"] if u != user["id"]), None)
                if other_id:
                    other = await db.users.find_one({"id": other_id}, {"_id": 0})
                    if other and other.get("is_seed"):
                        import random
                        replies = [
                            f"omg {user.get('name', 'you')}, hi 👋",
                            "wait — do we actually look alike?",
                            "ok, you're cute. continue.",
                            "send a selfie selfie. for science.",
                            "what's your chaos mode pick rn?",
                            "I'm into it ✨",
                        ]
                        reply = {
                            "id": str(uuid.uuid4()),
                            "match_id": match_id,
                            "sender_id": other_id,
                            "body": random.choice(replies),
                            "created_at": now_iso(),
                            "read": False,
                            "auto": True,
                        }
                        await db.messages.insert_one(reply)
                        for peer in list(room):
                            try:
                                await peer.send_json({"type": "message", "message": {**reply, "_id": None}})
                            except Exception:
                                room.discard(peer)
            elif t == "typing":
                for peer in list(room):
                    if peer is websocket:
                        continue
                    try:
                        await peer.send_json({"type": "typing", "user_id": user["id"]})
                    except Exception:
                        room.discard(peer)
            elif t == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        room.discard(websocket)
        if not room:
            _ws_rooms.pop(match_id, None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

from seed_data import get_seed_profiles_with_embeddings
from storage import APP_NAME, get_object, init_storage, put_object

# ---------------------------------------------------------------------------
# Config & DB
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_TTL_DAYS = 30

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

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
                "created_at": now_iso(),
            }
        )
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
        "onboarding_complete": True,
        "onboarded_at": now_iso(),
    }
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
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
    """Return ranked candidate profiles for the current user."""
    active_mode = mode or user.get("mode", "doppel")
    looking_for = user.get("looking_for", "everyone")
    user_embedding = user.get("embedding") or []
    swiped_ids = {
        s["target_id"]
        async for s in db.swipes.find({"user_id": user["id"]}, {"target_id": 1})
    }

    query: dict = {"id": {"$ne": user["id"], "$nin": list(swiped_ids)}}
    gf = _gender_filter(looking_for)
    if gf:
        query["gender"] = {"$in": gf}

    candidates = await db.users.find(query, {"_id": 0}).to_list(500)
    # Filter to only those with an embedding & photo
    candidates = [c for c in candidates if c.get("embedding") and c.get("photo_url")]

    if user_embedding:
        scored = [
            (cosine_similarity(user_embedding, c["embedding"]), c) for c in candidates
        ]
    else:
        scored = [(0.0, c) for c in candidates]

    if active_mode == "doppel":
        scored.sort(key=lambda x: x[0], reverse=True)
    else:  # chaos => most different / shuffle bottom half
        scored.sort(key=lambda x: x[0])

    out = []
    for sim, c in scored[:limit]:
        # Map cosine [-1,1] -> percent [0,100]; clamp for display
        pct = max(0, min(100, int(round((sim + 1) * 50))))
        # For Chaos mode display "twist" score = 100 - pct
        display = pct if active_mode == "doppel" else max(0, 100 - pct)
        out.append(
            {
                **public_profile(c),
                "score": display,
                "mode": active_mode,
            }
        )
    return {"mode": active_mode, "results": out}


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
    since: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    await _match_or_403(match_id, user["id"])
    query: dict = {"match_id": match_id}
    if since:
        query["created_at"] = {"$gt": since}
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


async def seed_profiles():
    """Insert seed/demo profiles if missing."""
    seeds = get_seed_profiles_with_embeddings()
    for s in seeds:
        existing = await db.users.find_one({"email": f"{s['username']}@seed.doppelcrush"})
        if existing:
            continue
        await db.users.insert_one(
            {
                "id": str(uuid.uuid4()),
                "email": f"{s['username']}@seed.doppelcrush",
                "name": s["name"],
                "age": s["age"],
                "gender": s["gender"],
                "bio": s["bio"],
                "photo_url": s["photo_url"],
                "location": s["location"],
                "embedding": s["embedding"],
                "looking_for": "everyone",
                "mode": "doppel",
                "onboarding_complete": True,
                "is_seed": True,
                "password_hash": hash_password(secrets.token_hex(16)),
                "referral_code": generate_referral_code(),
                "created_at": now_iso(),
            }
        )
    logger.info("Seed profiles ensured.")


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

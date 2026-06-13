"""DoppelCrush backend — FastAPI entrypoint.

This module is intentionally thin: it wires the lifespan, middleware,
routers, the WebSocket chat upgrade, and the startup seed hook. All
business logic lives in `routers/*.py`, `deps.py`, `matching.py`,
`moderation.py`, and `storage.py`.
"""
from __future__ import annotations

import logging
import os
import random
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import jwt
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# `deps` loads .env on import, sets up the Mongo client and shared singletons.
from deps import (
    JWT_ALG,
    JWT_SECRET,
    db,
    generate_referral_code,
    hash_password,
    mongo_client,
    now_iso,
    vector_store,
)
from matching import MODEL_SYNTHETIC
from routers import auth, chat, files, match, viral
from seed_data import get_seed_profiles_with_embeddings
from storage import init_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doppelcrush")


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------
async def ensure_indexes() -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("referral_code", unique=True, sparse=True)
    await db.swipes.create_index([("user_id", 1), ("target_id", 1)])
    await db.matches.create_index("users")
    await db.messages.create_index([("match_id", 1), ("created_at", 1)])
    await db.files.create_index("storage_path")
    await db.face_embeddings.create_index("user_id", unique=True)


async def seed_profiles() -> None:
    """Insert seed/demo profiles if missing AND populate face_embeddings."""
    seeds = get_seed_profiles_with_embeddings()
    for s in seeds:
        existing = await db.users.find_one(
            {"email": f"{s['username']}@seed.doppelcrush"}
        )
        if existing:
            await vector_store.upsert(
                existing["id"],
                s["embedding"],
                {
                    "model_version": MODEL_SYNTHETIC,
                    "quality_score": 0.7,
                    "face_detected": True,
                },
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
            {
                "model_version": MODEL_SYNTHETIC,
                "quality_score": 0.7,
                "face_detected": True,
            },
        )
    logger.info("Seed profiles + embeddings ensured.")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    await seed_profiles()
    try:
        init_storage()
    except Exception as e:  # noqa: BLE001
        logger.warning("Storage init deferred: %s", e)
    yield
    mongo_client.close()


app = FastAPI(title="DoppelCrush API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/")
async def root() -> dict:
    return {"ok": True, "service": "DoppelCrush"}


# Routers (all are prefixed `/api`)
app.include_router(auth.router)
app.include_router(match.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(viral.router)


# ---------------------------------------------------------------------------
# WebSocket — optional real-time upgrade for chat (polling remains fallback)
# ---------------------------------------------------------------------------
_ws_rooms: dict[str, set[WebSocket]] = {}

_SEED_REPLIES = [
    "omg {name}, hi 👋",
    "wait — do we actually look alike?",
    "ok, you're cute. continue.",
    "send a selfie selfie. for science.",
    "what's your chaos mode pick rn?",
    "I'm into it ✨",
]


async def _ws_authenticate(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    return await db.users.find_one({"id": payload["sub"]}, {"_id": 0})


async def _broadcast(room: set[WebSocket], payload: dict) -> None:
    for peer in list(room):
        try:
            await peer.send_json(payload)
        except Exception:
            room.discard(peer)


@app.websocket("/api/ws/chat/{match_id}")
async def ws_chat(websocket: WebSocket, match_id: str, token: str = Query("")):
    user = await _ws_authenticate(token)
    if not user:
        await websocket.close(code=4401)
        return
    match = await db.matches.find_one(
        {"id": match_id, "users": user["id"]}, {"_id": 0}
    )
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
                await _broadcast(
                    room, {"type": "message", "message": {**msg, "_id": None}}
                )
                # Auto-reply from seed profile for demo feel (parity with HTTP).
                other_id = next(
                    (u for u in match["users"] if u != user["id"]), None
                )
                if other_id:
                    other = await db.users.find_one({"id": other_id}, {"_id": 0})
                    if other and other.get("is_seed"):
                        reply_body = random.choice(_SEED_REPLIES).format(
                            name=user.get("name", "you")
                        )
                        reply = {
                            "id": str(uuid.uuid4()),
                            "match_id": match_id,
                            "sender_id": other_id,
                            "body": reply_body,
                            "created_at": now_iso(),
                            "read": False,
                            "auto": True,
                        }
                        await db.messages.insert_one(reply)
                        await _broadcast(
                            room,
                            {"type": "message", "message": {**reply, "_id": None}},
                        )
            elif t == "typing":
                for peer in list(room):
                    if peer is websocket:
                        continue
                    try:
                        await peer.send_json(
                            {"type": "typing", "user_id": user["id"]}
                        )
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

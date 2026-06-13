"""Viral growth: shares, referrals, twin teaser, compare rooms."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from deps import (
    client_ip,
    db,
    get_current_user,
    now_iso,
    public_profile,
    rate_limit,
)
from matching import cosine_sim
from models import CompareCreateIn, ShareEventIn

router = APIRouter(prefix="/api")


@router.post("/share")
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
    await db.users.update_one({"id": user["id"]}, {"$inc": {"extra_daily_matches": 1}})
    return {"ok": True}


@router.get("/referral/{code}")
async def referral_info(code: str):
    user = await db.users.find_one({"referral_code": code}, {"_id": 0})
    if not user:
        return {"valid": False}
    return {
        "valid": True,
        "name": user.get("name"),
        "photo_url": user.get("photo_url"),
    }


@router.get("/share/twin/{user_id}")
async def twin_teaser(user_id: str, request: Request):
    """Public viral landing data. Light rate limit per client IP."""
    if not rate_limit(f"twin:{client_ip(request)}", max_calls=30, window_sec=60.0):
        raise HTTPException(status_code=429, detail="Too many requests")
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


@router.post("/compare")
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


@router.post("/compare/{room_id}/join")
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


@router.get("/compare/{room_id}")
async def get_compare(room_id: str, user: dict = Depends(get_current_user)):
    room = await db.compare_rooms.find_one({"id": room_id}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user["id"] not in room["participants"]:
        await db.compare_rooms.update_one(
            {"id": room_id},
            {"$addToSet": {"participants": user["id"]}},
        )
        room["participants"].append(user["id"])

    users = await db.users.find(
        {"id": {"$in": room["participants"]}}, {"_id": 0}
    ).to_list(50)
    pairs = []
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            a, b = users[i], users[j]
            if not a.get("embedding") or not b.get("embedding"):
                continue
            sim = cosine_sim(a["embedding"], b["embedding"])
            pct = max(0, min(100, int(round((sim + 1) * 50))))
            pairs.append({"a": public_profile(a), "b": public_profile(b), "score": pct})
    pairs.sort(key=lambda p: p["score"], reverse=True)
    strongest_twin = pairs[0] if pairs else None
    chaos_contrast = pairs[-1] if len(pairs) > 1 else None
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


__all__ = ["router"]

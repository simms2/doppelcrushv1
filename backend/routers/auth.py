"""Auth + profile + user-scoped endpoints."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import (
    create_access_token,
    db,
    generate_referral_code,
    get_current_user,
    hash_password,
    MODEL_FACEAPI,
    now_iso,
    public_profile,
    vector_store,
    verify_password,
)
from models import LoginIn, OnboardingIn, ProfilePatch, SignupIn

router = APIRouter(prefix="/api")


@router.post("/auth/signup")
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
    twin_room_id: Optional[str] = None
    if data.twin_id:
        twin = await db.users.find_one({"id": data.twin_id}, {"_id": 0})
        if twin:
            twin_room_id = str(uuid.uuid4())[:8]
            await db.compare_rooms.insert_one({
                "id": twin_room_id,
                "host_id": twin["id"],
                "title": f"You vs {twin.get('name','your twin')}",
                "participants": [twin["id"], user_id],
                "source": "twin_share",
                "created_at": now_iso(),
            })
    token = create_access_token(user_id)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return {"token": token, "user": doc, "twin_room_id": twin_room_id}


@router.post("/auth/login")
async def login(data: LoginIn):
    email = data.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"])
    user.pop("password_hash", None)
    return {"token": token, "user": user}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    user.pop("password_hash", None)
    user.pop("embedding", None)
    return user


@router.post("/onboarding")
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


@router.patch("/me/mode")
async def update_mode(body: dict, user: dict = Depends(get_current_user)):
    mode = body.get("mode")
    if mode not in ("doppel", "chaos"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    await db.users.update_one({"id": user["id"]}, {"$set": {"mode": mode}})
    return {"mode": mode}


@router.patch("/me")
async def patch_me(data: ProfilePatch, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not updates:
        return user
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
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


@router.delete("/me")
async def delete_me(user: dict = Depends(get_current_user)):
    uid = user["id"]
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


@router.get("/me/stats")
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


@router.get("/me/unread")
async def my_unread(user: dict = Depends(get_current_user)):
    pipeline = [
        {"$match": {"sender_id": {"$ne": user["id"]}, "read": False}},
        {"$lookup": {"from": "matches", "localField": "match_id", "foreignField": "id", "as": "m"}},
        {"$match": {"m.users": user["id"]}},
        {"$count": "n"},
    ]
    result = await db.messages.aggregate(pipeline).to_list(1)
    n = result[0]["n"] if result else 0
    return {"unread": n}


@router.get("/me/compare-rooms")
async def my_compare_rooms(user: dict = Depends(get_current_user)):
    rooms = await db.compare_rooms.find(
        {"participants": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return [
        {
            "id": r["id"],
            "title": r.get("title"),
            "participant_count": len(r.get("participants", [])),
            "source": r.get("source"),
            "created_at": r["created_at"],
        }
        for r in rooms
    ]


__all__ = ["router"]

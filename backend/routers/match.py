"""Discover, swipe, matches list/get, openers."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user, match_or_403, now_iso, public_profile, ranker
from models import SwipeIn

router = APIRouter(prefix="/api")


@router.get("/discover")
async def discover(
    mode: Optional[str] = None,
    limit: int = 12,
    user: dict = Depends(get_current_user),
):
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


@router.post("/swipe")
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
    match_id: Optional[str] = None
    if data.direction == "like":
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


@router.get("/matches")
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


@router.get("/matches/{match_id}")
async def get_match(match_id: str, user: dict = Depends(get_current_user)):
    match = await match_or_403(match_id, user["id"])
    other_id = next((u for u in match["users"] if u != user["id"]), None)
    other = await db.users.find_one({"id": other_id}, {"_id": 0}) if other_id else None
    return {
        "id": match["id"],
        "created_at": match["created_at"],
        "profile": public_profile(other) if other else None,
    }


@router.get("/matches/{match_id}/openers")
async def get_openers(match_id: str, user: dict = Depends(get_current_user)):
    match = await match_or_403(match_id, user["id"])
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


__all__ = ["router"]

"""Chat messaging, typing indicator, conversation state."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from deps import db, get_current_user, match_or_403, now_iso
from models import MessageIn

router = APIRouter(prefix="/api")


@router.get("/matches/{match_id}/messages")
async def list_messages(
    match_id: str,
    since: Optional[datetime] = Query(None),
    user: dict = Depends(get_current_user),
):
    await match_or_403(match_id, user["id"])
    query: dict = {"match_id": match_id}
    if since:
        query["created_at"] = {"$gt": since.isoformat()}
    msgs = (
        await db.messages.find(query, {"_id": 0})
        .sort("created_at", 1)
        .to_list(500)
    )
    await db.messages.update_many(
        {"match_id": match_id, "sender_id": {"$ne": user["id"]}, "read": False},
        {"$set": {"read": True}},
    )
    return msgs


@router.post("/matches/{match_id}/messages")
async def send_message(
    match_id: str,
    data: MessageIn,
    user: dict = Depends(get_current_user),
):
    match = await match_or_403(match_id, user["id"])
    msg = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "sender_id": user["id"],
        "body": data.body.strip(),
        "created_at": now_iso(),
        "read": False,
    }
    await db.messages.insert_one(msg)
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
            await db.messages.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "match_id": match_id,
                    "sender_id": other_id,
                    "body": random.choice(replies),
                    "created_at": now_iso(),
                    "read": False,
                    "auto": True,
                }
            )
    msg.pop("_id", None)
    return msg


@router.post("/matches/{match_id}/typing")
async def post_typing(match_id: str, user: dict = Depends(get_current_user)):
    await match_or_403(match_id, user["id"])
    await db.typing.update_one(
        {"match_id": match_id, "user_id": user["id"]},
        {"$set": {"updated_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True}


@router.get("/matches/{match_id}/state")
async def match_state(match_id: str, user: dict = Depends(get_current_user)):
    match = await match_or_403(match_id, user["id"])
    other_id = next((u for u in match["users"] if u != user["id"]), None)
    typing = False
    if other_id:
        t = await db.typing.find_one({"match_id": match_id, "user_id": other_id})
        if t:
            updated = datetime.fromisoformat(t["updated_at"])
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


__all__ = ["router"]

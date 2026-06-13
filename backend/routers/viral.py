"""Viral growth: shares, referrals, twin teaser, compare rooms."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from html import escape as h
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

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
from share_render import render_twin_og
from storage import get_object

router = APIRouter(prefix="/api")
logger = logging.getLogger("doppelcrush.viral")


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


# ---------------------------------------------------------------------------
# OG / share-page helpers (rich-link previews for iMessage, WhatsApp, Slack…)
# ---------------------------------------------------------------------------
async def _fetch_user_photo_bytes(photo_url: Optional[str]) -> Optional[bytes]:
    """Best-effort fetch of a user's selfie for embedding in the OG card."""
    if not photo_url:
        return None
    # If the photo is stored in Emergent object storage we have a relative
    # /api/files/<path> URL. Read directly via the storage helper to avoid a
    # network roundtrip (run in a thread so we don't block the event loop).
    if "/api/files/" in photo_url:
        try:
            storage_path = photo_url.split("/api/files/", 1)[1]
            data, _ = await asyncio.to_thread(get_object, storage_path)
            return data
        except Exception as e:  # noqa: BLE001
            logger.info("OG photo storage fetch failed: %s", e)
            return None
    if photo_url.startswith("data:"):
        try:
            import base64
            return base64.b64decode(photo_url.split(",", 1)[1])
        except Exception:
            return None
    if photo_url.startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(photo_url)
                r.raise_for_status()
                return r.content
        except Exception as e:  # noqa: BLE001
            logger.info("OG photo http fetch failed: %s", e)
            return None
    return None


@router.get("/og/twin/{user_id}.png")
async def og_twin_image(user_id: str, request: Request):
    """Dynamic 1200x630 PNG used as the og:image for `/your-twin/:user_id`.

    Always returns a 200 PNG (falls back to a generic brand card when the
    user can't be loaded) so rich-link unfurlers don't cache 404s.
    """
    if not rate_limit(f"ogimg:{client_ip(request)}", max_calls=60, window_sec=60.0):
        raise HTTPException(status_code=429, detail="Too many requests")
    u = await db.users.find_one(
        {"id": user_id, "onboarding_complete": True, "moderation_state": {"$ne": "blocked"}},
        {"_id": 0, "password_hash": 0, "embedding": 0, "email": 0},
    )
    if not u:
        png = render_twin_og(
            name="DoppelCrush",
            photo_bytes=None,
            referral_code="",
            mode="doppel",
        )
    else:
        photo_bytes = await _fetch_user_photo_bytes(u.get("photo_url"))
        png = render_twin_og(
            name=u.get("name") or "your twin",
            photo_bytes=photo_bytes,
            referral_code=u.get("referral_code") or "",
            mode=u.get("mode", "doppel"),
        )
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600, s-maxage=86400",
        },
    )


@router.get("/share/twin-page/{user_id}", response_class=HTMLResponse)
async def twin_share_page(user_id: str, request: Request):
    """Crawler-friendly HTML wrapper for the `/your-twin/:user_id` SPA.

    Returns OG / Twitter card meta tags so iMessage/WhatsApp/Slack/Twitter
    show a rich preview. Human visitors are redirected to the React route
    via meta-refresh + JS fallback.
    """
    if not rate_limit(f"twinpage:{client_ip(request)}", max_calls=60, window_sec=60.0):
        raise HTTPException(status_code=429, detail="Too many requests")
    u = await db.users.find_one(
        {"id": user_id, "onboarding_complete": True, "moderation_state": {"$ne": "blocked"}},
        {"_id": 0, "password_hash": 0, "embedding": 0, "email": 0},
    )
    public_base = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
    # Honour the gateway's forwarded headers so the absolute URLs we emit
    # match the user-visible domain (and use https for rich-link crawlers).
    fwd_proto = request.headers.get("x-forwarded-proto", "https")
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if public_base:
        backend_origin = public_base
    elif fwd_host:
        backend_origin = f"{fwd_proto}://{fwd_host}"
    else:
        backend_origin = str(request.base_url).rstrip("/")
    app_url = f"{backend_origin}/your-twin/{user_id}"
    og_image = f"{backend_origin}/api/og/twin/{user_id}.png"

    if not u:
        name = "DoppelCrush"
        desc = "Find your DoppelCrush — twin energy or chaos. Selfie first, crush later."
    else:
        name = u.get("name") or "DoppelCrush"
        mode = u.get("mode", "doppel")
        if mode == "chaos":
            desc = f"Meet {name} on DoppelCrush. Plot twist energy. Join the chaos."
        else:
            desc = f"Meet {name} on DoppelCrush. Twin energy. Same face, same vibe."

    title = f"Meet {name} on DoppelCrush"
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}" />

<meta property="og:type" content="profile" />
<meta property="og:site_name" content="DoppelCrush" />
<meta property="og:title" content="{h(title)}" />
<meta property="og:description" content="{h(desc)}" />
<meta property="og:url" content="{h(app_url)}" />
<meta property="og:image" content="{h(og_image)}" />
<meta property="og:image:secure_url" content="{h(og_image)}" />
<meta property="og:image:type" content="image/png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="{h(title)}" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{h(title)}" />
<meta name="twitter:description" content="{h(desc)}" />
<meta name="twitter:image" content="{h(og_image)}" />

<link rel="canonical" href="{h(app_url)}" />
<meta http-equiv="refresh" content="0; url={h(app_url)}" />
<style>body{{font-family:system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;background:linear-gradient(135deg,#ffd84d,#ff2d8a 50%,#ff6a3d);color:#0f172a;text-align:center;padding:24px}}a{{color:#0f172a;font-weight:700}}</style>
</head>
<body>
<noscript>
  <p>You need JavaScript enabled to view this page.</p>
  <p><a href="{h(app_url)}">Continue to DoppelCrush →</a></p>
</noscript>
<script>window.location.replace({app_url!r});</script>
<p>Opening DoppelCrush… <a href="{h(app_url)}">Tap here if it doesn't open.</a></p>
</body>
</html>"""
    return HTMLResponse(
        content=html_doc,
        headers={"Cache-Control": "public, max-age=300, s-maxage=3600"},
    )


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

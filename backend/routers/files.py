"""Selfie upload and file serving (object storage)."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from deps import db, get_current_user, now_iso
from models import MIME_BY_EXT
from moderation import check_selfie
from storage import APP_NAME, get_object, put_object

logger = logging.getLogger("doppelcrush.files")
router = APIRouter(prefix="/api")


@router.post("/upload/selfie")
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
    except Exception as e:
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
    import os
    backend = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
    file_path = result["path"]
    return {
        "path": file_path,
        "url": f"{backend}/api/files/{file_path}" if backend else f"/api/files/{file_path}",
    }


@router.get("/files/{path:path}")
async def serve_file(path: str):
    record = await db.files.find_one(
        {"storage_path": path, "is_deleted": False}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, ctype = get_object(path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage read failed: {e}")
    return Response(
        content=data,
        media_type=record.get("content_type", ctype),
        headers={"Cache-Control": "public, max-age=86400"},
    )


__all__ = ["router"]

"""Pydantic request/response models for DoppelCrush."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from matching import MODEL_FACEAPI

Gender = Literal["woman", "man", "nonbinary"]
LookingFor = Literal["women", "men", "everyone"]
Mode = Literal["doppel", "chaos"]


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=40)
    ref: Optional[str] = None
    twin_id: Optional[str] = None
    source: Optional[str] = None


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


class ProfilePatch(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    mode: Optional[Mode] = None
    looking_for: Optional[LookingFor] = None
    photo_url: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    embedding_model: Optional[str] = None


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

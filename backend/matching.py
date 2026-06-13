"""
DoppelCrush matching pipeline.

Architecture (production-minded, swappable for scale):

  selfie  ─► face-api.js (browser) ─► validated embedding + quality_score
                                              │
                                              ▼
                              POST /api/me/embedding
                                              │
                                              ▼
                       VectorStore.upsert(user_id, emb, meta)
                                              │
            ┌────────────────── candidate filter ─────────────────┐
            │  onboarding_complete, looking_for, age range,        │
            │  not blocked, not already swiped, moderation_ok      │
            └──────────────────────────────────────────────────────┘
                                              │
                                              ▼
                       VectorStore.query_topk(emb, predicate, k)
                       (ANN at scale — pgvector / Qdrant / FAISS)
                                              │
                                              ▼
                           Ranker.rerank(candidates, mode)
                                              │
                                              ▼
                          [{user, score, explanation}, ...]

For the MVP we ship a Mongo-backed in-memory linear scan that obeys the same
interface as a real ANN store; swap one class to move to pgvector/Qdrant.
"""
from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Optional

logger = logging.getLogger("doppelcrush.matching")

# ── Constants ──────────────────────────────────────────────────────────────
EMBEDDING_DIM = 128
MODEL_FACEAPI = "face-api.js@0.22.2/face_recognition_net"
MODEL_SYNTHETIC = "synthetic-v1"  # demo seeds

# Chaos contrast band: similar enough to be recognisable, different enough to
# feel like a plot twist. Calibrated for face-api descriptors.
CHAOS_BAND_FACEAPI = (0.30, 0.55)
CHAOS_BAND_SYNTHETIC = (-0.10, 0.10)

# Minimum acceptable selfie quality (0..1) — anything below is rejected upstream
MIN_QUALITY = 0.40


# ── Math helpers ───────────────────────────────────────────────────────────
def l2_normalise(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _hash_jitter(a: str, b: str) -> float:
    """Deterministic value in [-0.5, 0.5] used to add gentle per-pair variance
    when comparing across model versions (e.g. synthetic vs face-api)."""
    h = hashlib.sha256(f"{a}|{b}".encode()).digest()
    return (h[0] / 255.0) - 0.5


def twin_energy_score(sim: float, candidate_model: str) -> int:
    """Map a raw cosine similarity to a 0-100 Twin Energy %.

    Real face-api descriptors: same-person ~0.85, similar ~0.55, stranger ~0.25.
    Synthetic seeds: cosine ~0 (random unit vectors), so we widen the mapping
    so seeds still produce visually plausible scores for the MVP demo.
    """
    if candidate_model == MODEL_SYNTHETIC:
        x = max(-0.25, min(0.25, sim))
        return int(round(40 + (x + 0.25) / 0.5 * 55))  # [-0.25..0.25] -> [40..95]
    if sim <= 0.30:
        return 0
    if sim >= 0.85:
        return 100
    return int(round((sim - 0.30) / 0.55 * 100))


def chaos_score(sim: float, candidate_model: str) -> int:
    """0-100 "Chaos Match" score. Mid-band gets the highest score; matches at
    band edges get lower scores. Synthetic uses a tighter band centred at 0."""
    lo, hi = CHAOS_BAND_SYNTHETIC if candidate_model == MODEL_SYNTHETIC else CHAOS_BAND_FACEAPI
    if sim < lo or sim > hi:
        return 0
    mid = (lo + hi) / 2
    dist = abs(sim - mid) / ((hi - lo) / 2)
    return int(round(100 * (1 - dist)))


# ── VectorStore abstraction ────────────────────────────────────────────────
class VectorStore(ABC):
    """Vector backend abstraction. Implementations:
       - MongoVectorStore: ships now (linear scan, fine up to ~10k profiles)
       - PgVectorStore: future drop-in via psycopg + ORDER BY embedding <-> q
       - QdrantStore / WeaviateStore: future ANN at millions scale.
    """

    @abstractmethod
    async def upsert(self, user_id: str, embedding: list[float], metadata: dict) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str) -> None: ...

    @abstractmethod
    async def query_topk(
        self,
        query_embedding: list[float],
        predicate: Optional[Callable[[dict], bool]] = None,
        k: int = 200,
    ) -> list[tuple[float, dict]]:
        """Return [(cosine_sim, embedding_doc), …] sorted DESC by sim."""


class MongoVectorStore(VectorStore):
    """MVP backend: store + retrieve embeddings from MongoDB's
    `face_embeddings` collection. Linear scan with predicate filtering."""

    COLLECTION = "face_embeddings"

    def __init__(self, db):
        self.db = db

    async def upsert(self, user_id: str, embedding: list[float], metadata: dict) -> None:
        emb = l2_normalise(embedding)
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "user_id": user_id,
            "embedding": emb,
            "model_version": metadata.get("model_version", MODEL_FACEAPI),
            "quality_score": float(metadata.get("quality_score", 0.6)),
            "face_detected": bool(metadata.get("face_detected", True)),
            "updated_at": now,
        }
        await self.db[self.COLLECTION].update_one(
            {"user_id": user_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    async def delete(self, user_id: str) -> None:
        await self.db[self.COLLECTION].delete_many({"user_id": user_id})

    async def query_topk(
        self,
        query_embedding: list[float],
        predicate: Optional[Callable[[dict], bool]] = None,
        k: int = 200,
    ) -> list[tuple[float, dict]]:
        q = l2_normalise(query_embedding)
        scored: list[tuple[float, dict]] = []
        async for doc in self.db[self.COLLECTION].find({}, {"_id": 0}):
            if predicate and not predicate(doc):
                continue
            sim = cosine_sim(q, doc.get("embedding") or [])
            scored.append((sim, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]


# ── Ranker ─────────────────────────────────────────────────────────────────
class Ranker:
    """Two-stage ranker: ANN retrieval ➜ product rerank.

    The vector store handles the "find me the top N closest faces" search;
    the ranker then re-orders those N with quality weighting and product
    explanations (Twin Energy / Chaos / etc.).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        user_loader: Callable[[Iterable[str]], Awaitable[dict[str, dict]]],
    ):
        self.vs = vector_store
        self.load_users = user_loader

    @staticmethod
    def _passes_filters(viewer: dict, candidate: dict, swiped: set[str]) -> bool:
        if candidate["id"] == viewer["id"]:
            return False
        if candidate["id"] in swiped:
            return False
        if not candidate.get("onboarding_complete"):
            return False
        if candidate.get("moderation_state") == "blocked":
            return False
        looking_for = viewer.get("looking_for", "everyone")
        gender = candidate.get("gender")
        if looking_for == "women" and gender != "woman":
            return False
        if looking_for == "men" and gender != "man":
            return False
        # age range (default +/- 10 yrs but allow wide tolerance for MVP)
        v_age = viewer.get("age")
        c_age = candidate.get("age")
        if v_age and c_age and abs(v_age - c_age) > 15:
            return False
        return True

    @staticmethod
    def _doppel_explain(sim: float, candidate_model: str) -> list[str]:
        score = twin_energy_score(sim, candidate_model)
        if score >= 85:
            return ["uncanny face card", "high facial similarity"]
        if score >= 65:
            return ["familiar vibe", "twin energy"]
        if score >= 40:
            return ["same energy"]
        return ["soft match"]

    @staticmethod
    def _chaos_explain(sim: float) -> list[str]:
        return ["plot twist energy", "contrast pick"]

    async def rank(
        self,
        viewer: dict,
        viewer_embedding: list[float],
        *,
        mode: str = "doppel",
        k: int = 24,
        retrieval_k: int = 400,
        swiped_ids: Optional[set[str]] = None,
    ) -> list[dict]:
        swiped = swiped_ids or set()
        # Stage 1: filter at vector-store level on cheap metadata
        def predicate(emb_doc: dict) -> bool:
            if emb_doc.get("user_id") == viewer["id"]:
                return False
            if emb_doc.get("quality_score", 0) < MIN_QUALITY:
                return False
            return True

        # Stage 2: ANN retrieve top-N
        raw = await self.vs.query_topk(viewer_embedding, predicate, k=retrieval_k)
        if not raw:
            return []
        # Stage 3: load user profiles for the candidates in ONE batch
        ids = [e["user_id"] for _, e in raw]
        profiles = await self.load_users(ids)

        scored: list[dict] = []
        for sim, ed in raw:
            cand = profiles.get(ed["user_id"])
            if not cand or not self._passes_filters(viewer, cand, swiped):
                continue
            quality = ed.get("quality_score", 0.5)
            model = ed.get("model_version", MODEL_FACEAPI)
            if mode == "chaos":
                lo, hi = CHAOS_BAND_SYNTHETIC if model == MODEL_SYNTHETIC else CHAOS_BAND_FACEAPI
                if sim < lo or sim > hi:
                    continue
                display = chaos_score(sim, model)
                mid = (lo + hi) / 2
                band_fit = 1 - abs(sim - mid) / max((hi - lo) / 2, 1e-6)
                final = 0.4 * band_fit + 0.4 * quality + 0.2 * (display / 100)
                explain = self._chaos_explain(sim)
            else:  # doppel (default)
                display = twin_energy_score(sim, model)
                # quality-weighted: penalise low-quality candidate selfies
                final = (display / 100) * (0.6 + 0.4 * quality)
                explain = self._doppel_explain(sim, model)
            scored.append({
                "profile": cand,
                "score": display,
                "_final": final,
                "_sim": round(sim, 4),
                "quality": round(quality, 3),
                "model_version": model,
                "explanation": explain,
                "mode": mode,
            })

        scored.sort(key=lambda x: x["_final"], reverse=True)
        return scored[:k]

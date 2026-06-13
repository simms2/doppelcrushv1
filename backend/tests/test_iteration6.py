"""Iteration 6 tests — twin share endpoints, signup twin_id wiring,
PgVectorStore stub, MIN_QUALITY filter push-down, WS route registration."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://facial-vibes.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _email(tag: str) -> str:
    return f"TEST_iter6_{tag}_{uuid.uuid4().hex[:8]}@example.com"


def _signup(payload):
    return requests.post(f"{API}/auth/signup", json=payload, timeout=30)


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _onboard(token, photo_url="https://example.com/p.jpg", age=27, location="NYC"):
    body = {
        "age": age,
        "gender": "woman",
        "looking_for": "everyone",
        "mode": "doppel",
        "bio": "Hello",
        "location": location,
        "photo_url": photo_url,
        "embedding": [0.1] * 128,
        "quality_score": 0.8,
    }
    return requests.post(f"{API}/onboarding", json=body, headers=_auth_headers(token), timeout=30)


@pytest.fixture(scope="module")
def inviter():
    """An onboarded user with a photo_url — to be 'twin' for share landing."""
    em = _email("inviter")
    r = _signup({"email": em, "password": "passw0rd!", "name": "TwinInviter"})
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["token"]
    user = data["user"]
    ob = _onboard(token, photo_url="https://example.com/twin.jpg", age=28, location="Brooklyn")
    assert ob.status_code == 200, ob.text
    return {"token": token, "user": user, "email": em, "referral_code": user["referral_code"]}


@pytest.fixture(scope="module")
def non_onboarded_user():
    em = _email("nonob")
    r = _signup({"email": em, "password": "passw0rd!", "name": "NotOnboarded"})
    assert r.status_code == 200
    return r.json()["user"]


# ── /api/share/twin/{user_id} ─────────────────────────────────────────────
class TestTwinShare:
    def test_public_no_auth_returns_teaser(self, inviter):
        # No Authorization header — must be PUBLIC
        r = requests.get(f"{API}/share/twin/{inviter['user']['id']}", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["valid"] is True
        u = data["user"]
        assert u["id"] == inviter["user"]["id"]
        assert u["name"] == "TwinInviter"
        assert u["photo_url"] == "https://example.com/twin.jpg"
        assert u["mode"] == "doppel"
        assert u["age_band"] == "25s"  # 28 // 5 * 5
        assert u["location"] == "Brooklyn"
        assert "bio" in u
        assert data["referral_code"] == inviter["referral_code"]

    def test_no_leak_of_sensitive_fields(self, inviter):
        r = requests.get(f"{API}/share/twin/{inviter['user']['id']}", timeout=20)
        body = r.json()
        # top-level
        assert "password_hash" not in body
        assert "email" not in body
        # nested user object
        u = body["user"]
        for forbidden in ("email", "password_hash", "embedding", "moderation_state"):
            assert forbidden not in u, f"Leaked field: {forbidden}"

    def test_unknown_user_returns_invalid(self):
        r = requests.get(f"{API}/share/twin/does-not-exist-{uuid.uuid4()}", timeout=20)
        assert r.status_code == 200
        assert r.json() == {"valid": False}

    def test_non_onboarded_returns_invalid(self, non_onboarded_user):
        r = requests.get(f"{API}/share/twin/{non_onboarded_user['id']}", timeout=20)
        assert r.status_code == 200
        assert r.json() == {"valid": False}


# ── Signup with twin_id auto-creates compare room ─────────────────────────
class TestSignupTwinIdCompareRoom:
    def test_signup_with_twin_id_creates_room_for_both(self, inviter):
        em = _email("newcomer")
        r = _signup({
            "email": em,
            "password": "passw0rd!",
            "name": "Newcomer",
            "twin_id": inviter["user"]["id"],
            "source": "twin_share",
        })
        assert r.status_code == 200, r.text
        new_user = r.json()["user"]
        new_token = r.json()["token"]

        # New user sees the room
        rooms_new = requests.get(f"{API}/me/compare-rooms", headers=_auth_headers(new_token), timeout=20)
        assert rooms_new.status_code == 200, rooms_new.text
        rooms_new_data = rooms_new.json()
        assert isinstance(rooms_new_data, list)
        twin_rooms_new = [r for r in rooms_new_data if r.get("source") == "twin_share"]
        assert len(twin_rooms_new) >= 1
        room = twin_rooms_new[0]
        assert room["title"] == "You vs TwinInviter"
        assert room["participant_count"] == 2
        assert "id" in room and "created_at" in room

        # Inviter ALSO sees the room
        rooms_inv = requests.get(f"{API}/me/compare-rooms", headers=_auth_headers(inviter["token"]), timeout=20)
        assert rooms_inv.status_code == 200
        inv_rooms = rooms_inv.json()
        matching = [r for r in inv_rooms if r.get("source") == "twin_share" and r["title"] == "You vs TwinInviter"]
        assert len(matching) >= 1

    def test_signup_with_bad_twin_id_still_succeeds(self):
        em = _email("badtwin")
        r = _signup({
            "email": em,
            "password": "passw0rd!",
            "name": "BadTwinUser",
            "twin_id": "nonexistent-id-xyz",
            "source": "twin_share",
        })
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        rooms = requests.get(f"{API}/me/compare-rooms", headers=_auth_headers(token), timeout=20)
        assert rooms.status_code == 200
        # No twin_share room should be created
        twin_rooms = [r for r in rooms.json() if r.get("source") == "twin_share"]
        assert len(twin_rooms) == 0

    def test_signup_with_ref_and_twin_increments_inviter(self, inviter):
        # Capture pre stats
        pre = requests.get(f"{API}/me/stats", headers=_auth_headers(inviter["token"]), timeout=20).json()
        em = _email("refandtwin")
        r = _signup({
            "email": em,
            "password": "passw0rd!",
            "name": "RefTwinUser",
            "ref": inviter["referral_code"],
            "twin_id": inviter["user"]["id"],
            "source": "twin_share",
        })
        assert r.status_code == 200, r.text
        post = requests.get(f"{API}/me/stats", headers=_auth_headers(inviter["token"]), timeout=20).json()
        assert post["friends_joined"] == pre["friends_joined"] + 1
        assert post["bonus_matches"] == pre["bonus_matches"] + 3


# ── /api/me/compare-rooms auth ────────────────────────────────────────────
class TestCompareRoomsAuth:
    def test_requires_auth(self):
        r = requests.get(f"{API}/me/compare-rooms", timeout=20)
        assert r.status_code == 401


# ── PgVectorStore stub + MIN_QUALITY filter ───────────────────────────────
class TestMatchingModule:
    def test_pgvectorstore_importable_and_stub(self):
        from matching import PgVectorStore, MIN_QUALITY
        assert MIN_QUALITY == 0.40
        store = PgVectorStore(pg_pool=None)
        import asyncio
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(store.upsert("u1", [0.0] * 128, {}))
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(store.delete("u1"))
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(store.query_topk([0.0] * 128, None, 10))

    def test_mongo_vector_store_filters_min_quality(self):
        """MongoVectorStore.query_topk should push quality_score>=MIN_QUALITY
        into the Mongo query (low-quality rows must be excluded)."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from matching import MongoVectorStore, MIN_QUALITY

        async def run():
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "test_database")]
            store = MongoVectorStore(db)
            low_id = f"TEST_lowq_{uuid.uuid4().hex[:8]}"
            high_id = f"TEST_highq_{uuid.uuid4().hex[:8]}"
            try:
                await store.upsert(low_id, [0.1] * 128, {"quality_score": 0.1, "model_version": "synthetic-v1"})
                await store.upsert(high_id, [0.1] * 128, {"quality_score": 0.9, "model_version": "synthetic-v1"})
                results = await store.query_topk([0.1] * 128, predicate=None, k=500)
                ids = [d.get("user_id") for _, d in results]
                assert high_id in ids, "High-quality embedding missing from results"
                assert low_id not in ids, f"Low-quality embedding leaked into results (MIN_QUALITY={MIN_QUALITY})"
            finally:
                await db.face_embeddings.delete_many({"user_id": {"$in": [low_id, high_id]}})
                client.close()

        asyncio.run(run())


# ── WebSocket route registration ──────────────────────────────────────────
class TestWebSocketRoute:
    def test_ws_route_registered(self):
        # Import server and check app.routes for the WS path
        import sys, importlib
        sys.path.insert(0, "/app/backend")
        srv = importlib.import_module("server")
        paths = [getattr(r, "path", None) for r in srv.app.routes]
        assert "/api/ws/chat/{match_id}" in paths, f"WS route not registered. Got: {paths}"

"""DoppelCrush iteration 3: selfie upload + chat between matched users.

Covers:
- POST /api/upload/selfie (multipart, auth, MIME validation, 8MB cap)
- GET /api/files/{path} (streaming, 404)
- POST /api/swipe returns match_id on like-to-seed
- GET /api/matches/{match_id} (auth, 404 on foreign access)
- POST /api/matches/{match_id}/messages (chat + seed auto-reply)
- GET /api/matches/{match_id}/messages (order, since filter, read flag)
"""
import io
import os
import time
import math
import hashlib
import struct
import zlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

TS = str(int(time.time()))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _embedding(seed: str, dim: int = 128):
    vec = []
    counter = 0
    while len(vec) < dim:
        h = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        for b in h:
            vec.append((b / 127.5) - 1.0)
            if len(vec) >= dim:
                break
        counter += 1
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _tiny_jpeg() -> bytes:
    """Smallest-possible valid baseline JPEG (~125 bytes)."""
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000"
        "ffdb004300080606070605080707070909080a0c"
        "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20"
        "242e2720222c231c1c2837292c30313434341f27"
        "393d38323c2e333432"
        "ffc0000b08000100010101110000"
        "ffc40014000100000000000000000000000000000000"
        "ffc40014100100000000000000000000000000000000"
        "ffda0008010100003f00"
        "37ffd9"
    )


def _tiny_png() -> bytes:
    """A 1x1 transparent PNG built programmatically."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr_chunk = b"IHDR" + ihdr
    ihdr_full = struct.pack(">I", 13) + ihdr_chunk + struct.pack(">I", zlib.crc32(ihdr_chunk) & 0xffffffff)
    raw = b"\x00\x00\x00\x00\x00"
    comp = zlib.compress(raw)
    idat_chunk = b"IDAT" + comp
    idat_full = struct.pack(">I", len(comp)) + idat_chunk + struct.pack(">I", zlib.crc32(idat_chunk) & 0xffffffff)
    iend_chunk = b"IEND"
    iend_full = struct.pack(">I", 0) + iend_chunk + struct.pack(">I", zlib.crc32(iend_chunk) & 0xffffffff)
    return sig + ihdr_full + idat_full + iend_full


def _signup(s, label, ref=None):
    email = f"{label}+{TS}@example.com"
    payload = {"email": email, "password": "crushme123", "name": label.capitalize()}
    if ref:
        payload["ref"] = ref
    r = s.post(f"{BASE_URL}/api/auth/signup", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    return {
        "email": email,
        "token": data["token"],
        "user": data["user"],
        "headers": {"Authorization": f"Bearer {data['token']}"},
    }


def _onboard(s, headers, label, gender="woman"):
    body = {
        "age": 24, "gender": gender, "looking_for": "everyone", "mode": "doppel",
        "bio": "test", "location": "SF",
        "photo_url": f"https://example.com/{label}.jpg",
        "embedding": _embedding(label),
    }
    r = s.post(f"{BASE_URL}/api/onboarding", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _pick_seed_target(s, headers) -> str:
    """Return a seed profile target_id from /discover."""
    r = s.get(f"{BASE_URL}/api/discover?limit=20", headers=headers)
    assert r.status_code == 200, r.text
    results = r.json().get("results", [])
    for p in results:
        if p.get("is_seed"):
            return p["id"]
    assert results, "no discover results at all"
    return results[0]["id"]


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def user_a(s):
    u = _signup(s, "iter3a")
    _onboard(s, u["headers"], "iter3a", "woman")
    return u


@pytest.fixture(scope="module")
def user_b(s):
    u = _signup(s, "iter3b")
    _onboard(s, u["headers"], "iter3b", "man")
    return u


@pytest.fixture(scope="module")
def match_for_a(s, user_a):
    """Like a seed profile to create a match for user_a, return match_id."""
    target_id = _pick_seed_target(s, user_a["headers"])
    r = s.post(
        f"{BASE_URL}/api/swipe",
        json={"target_id": target_id, "direction": "like"},
        headers=user_a["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["match"] is True, f"expected match on seed, got {data}"
    assert data.get("match_id"), f"match_id missing/null: {data}"
    return {"match_id": data["match_id"], "target_id": target_id, "target": data["target"]}


# --------------------------------------------------------------------------
# Upload tests
# --------------------------------------------------------------------------
class TestUploadSelfie:
    def test_upload_requires_auth(self, s):
        r = s.post(
            f"{BASE_URL}/api/upload/selfie",
            files={"file": ("a.jpg", _tiny_jpeg(), "image/jpeg")},
        )
        assert r.status_code == 401, r.text

    def test_upload_rejects_unsupported_extension(self, s, user_a):
        r = s.post(
            f"{BASE_URL}/api/upload/selfie",
            files={"file": ("evil.gif", b"GIF89a", "image/gif")},
            headers=user_a["headers"],
        )
        assert r.status_code == 400, r.text
        assert "JPG" in r.text or "allowed" in r.text.lower()

    def test_upload_rejects_oversize_file(self, s, user_a):
        big = b"\xff" * (8 * 1024 * 1024 + 100)
        r = s.post(
            f"{BASE_URL}/api/upload/selfie",
            files={"file": ("big.jpg", big, "image/jpeg")},
            headers=user_a["headers"],
        )
        assert r.status_code == 413, r.text

    def test_upload_jpeg_success_and_download(self, s, user_a):
        jpeg_bytes = _tiny_jpeg()
        r = s.post(
            f"{BASE_URL}/api/upload/selfie",
            files={"file": ("me.jpg", jpeg_bytes, "image/jpeg")},
            headers=user_a["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "path" in body and body["path"], body
        assert "url" in body and "/api/files/" in body["url"], body
        # Download back
        r2 = s.get(f"{BASE_URL}/api/files/{body['path']}")
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("content-type", "").startswith("image/jpeg"), r2.headers
        # Body should match what we uploaded
        assert r2.content == jpeg_bytes, "downloaded bytes != uploaded bytes"

    def test_upload_png_success(self, s, user_a):
        png_bytes = _tiny_png()
        r = s.post(
            f"{BASE_URL}/api/upload/selfie",
            files={"file": ("me.png", png_bytes, "image/png")},
            headers=user_a["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        r2 = s.get(f"{BASE_URL}/api/files/{body['path']}")
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image/png")

    def test_files_404_on_unknown_path(self, s):
        r = s.get(f"{BASE_URL}/api/files/doppelcrush/selfies/does-not-exist/xxx.jpg")
        assert r.status_code == 404, r.text


# --------------------------------------------------------------------------
# Swipe match_id
# --------------------------------------------------------------------------
class TestSwipeMatchId:
    def test_like_seed_returns_match_id(self, match_for_a):
        assert match_for_a["match_id"], "match_id should be non-null"
        # uuid-ish
        assert len(match_for_a["match_id"]) >= 8


# --------------------------------------------------------------------------
# Match detail + foreign access
# --------------------------------------------------------------------------
class TestGetMatch:
    def test_requires_auth(self, s, match_for_a):
        r = s.get(f"{BASE_URL}/api/matches/{match_for_a['match_id']}")
        assert r.status_code == 401

    def test_get_match_returns_profile(self, s, user_a, match_for_a):
        r = s.get(
            f"{BASE_URL}/api/matches/{match_for_a['match_id']}",
            headers=user_a["headers"],
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == match_for_a["match_id"]
        assert data["profile"] is not None
        assert data["profile"]["id"] == match_for_a["target_id"]

    def test_unknown_match_id_404(self, s, user_a):
        r = s.get(
            f"{BASE_URL}/api/matches/00000000-0000-0000-0000-000000000000",
            headers=user_a["headers"],
        )
        assert r.status_code == 404, r.text

    def test_foreign_user_cannot_access_match(self, s, user_b, match_for_a):
        r = s.get(
            f"{BASE_URL}/api/matches/{match_for_a['match_id']}",
            headers=user_b["headers"],
        )
        assert r.status_code == 404, r.text


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------
class TestMessages:
    def test_list_messages_requires_auth(self, s, match_for_a):
        r = s.get(f"{BASE_URL}/api/matches/{match_for_a['match_id']}/messages")
        assert r.status_code == 401

    def test_send_message_requires_auth(self, s, match_for_a):
        r = s.post(
            f"{BASE_URL}/api/matches/{match_for_a['match_id']}/messages",
            json={"body": "hi"},
        )
        assert r.status_code == 401

    def test_send_message_creates_two_with_seed_auto_reply(self, s, user_a, match_for_a):
        mid = match_for_a["match_id"]
        # purge state? we just rely on counts being >= 2 after this send
        before = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages", headers=user_a["headers"]
        ).json()
        baseline = len(before)
        r = s.post(
            f"{BASE_URL}/api/matches/{mid}/messages",
            json={"body": "hello doppel"},
            headers=user_a["headers"],
        )
        assert r.status_code == 200, r.text
        sent = r.json()
        assert sent["body"] == "hello doppel"
        assert sent["sender_id"] == user_a["user"]["id"]
        # Wait a moment then list
        time.sleep(0.4)
        after = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages", headers=user_a["headers"]
        ).json()
        # baseline + outbound + seed auto-reply = baseline + 2
        assert len(after) >= baseline + 2, (
            f"expected at least {baseline + 2} msgs, got {len(after)}: {after}"
        )
        # chronological order
        ts = [m["created_at"] for m in after]
        assert ts == sorted(ts), f"messages not chronological: {ts}"

    def test_messages_marked_read_after_listing(self, s, user_a, match_for_a):
        mid = match_for_a["match_id"]
        msgs = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages", headers=user_a["headers"]
        ).json()
        # All inbound (sender != user_a) should be read=True now
        inbound = [m for m in msgs if m["sender_id"] != user_a["user"]["id"]]
        assert inbound, "expected at least one inbound seed auto-reply"
        assert all(m.get("read") is True for m in inbound), (
            f"some inbound msgs not marked read: {inbound}"
        )

    def test_since_filter_returns_only_newer(self, s, user_a, match_for_a):
        mid = match_for_a["match_id"]
        all_msgs = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages", headers=user_a["headers"]
        ).json()
        assert all_msgs, "no messages to filter"
        cutoff = all_msgs[-1]["created_at"]
        # since = newest -> should return zero results (use params= so '+' is %2B-encoded)
        empty = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages",
            params={"since": cutoff},
            headers=user_a["headers"],
        ).json()
        assert empty == [], f"since filter should yield none, got {empty}"
        # Send a new one and verify since returns only that
        time.sleep(0.4)
        r = s.post(
            f"{BASE_URL}/api/matches/{mid}/messages",
            json={"body": "after cutoff"},
            headers=user_a["headers"],
        )
        assert r.status_code == 200
        time.sleep(0.4)
        newer = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages",
            params={"since": cutoff},
            headers=user_a["headers"],
        ).json()
        bodies = [m["body"] for m in newer]
        assert "after cutoff" in bodies, f"new msg not in since-filtered list: {newer}"

    def test_foreign_user_send_message_404(self, s, user_b, match_for_a):
        mid = match_for_a["match_id"]
        r = s.post(
            f"{BASE_URL}/api/matches/{mid}/messages",
            json={"body": "i shouldn't be here"},
            headers=user_b["headers"],
        )
        assert r.status_code == 404, r.text

    def test_foreign_user_list_messages_404(self, s, user_b, match_for_a):
        mid = match_for_a["match_id"]
        r = s.get(
            f"{BASE_URL}/api/matches/{mid}/messages",
            headers=user_b["headers"],
        )
        assert r.status_code == 404, r.text

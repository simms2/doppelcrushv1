"""DoppelCrush iteration 2: new endpoints + share kinds.

Covers:
- GET /api/me/stats
- POST /api/compare, /api/compare/{id}/join, GET /api/compare/{id}
- POST /api/share accepts 'story' and 'square'
- Signup with ref increments inviter friends_joined and bonus_matches
"""
import os
import time
import math
import hashlib
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

TS = str(int(time.time()))


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
        "age": 23, "gender": gender, "looking_for": "everyone", "mode": "doppel",
        "bio": "test", "location": "NYC",
        "photo_url": f"https://example.com/{label}.jpg",
        "embedding": _embedding(label),
    }
    r = s.post(f"{BASE_URL}/api/onboarding", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def primary(s):
    u = _signup(s, "primary2")
    _onboard(s, u["headers"], "primary2", "woman")
    return u


@pytest.fixture(scope="module")
def second(s):
    u = _signup(s, "second2")
    _onboard(s, u["headers"], "second2", "man")
    return u


@pytest.fixture(scope="module")
def third(s):
    u = _signup(s, "third2")
    _onboard(s, u["headers"], "third2", "nonbinary")
    return u


# ---- /api/me/stats ----
def test_stats_requires_auth(s):
    r = s.get(f"{BASE_URL}/api/me/stats")
    assert r.status_code == 401


def test_stats_returns_expected_keys(s, primary):
    r = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ("friends_joined", "bonus_matches", "shares", "matches", "referral_code"):
        assert key in data, f"missing key {key}"
    assert isinstance(data["friends_joined"], int)
    assert isinstance(data["bonus_matches"], int)
    assert isinstance(data["shares"], int)
    assert isinstance(data["matches"], int)
    assert data["referral_code"] == primary["user"]["referral_code"]


# ---- Referral increments friends_joined + bonus_matches +3 ----
def test_signup_with_ref_increments_inviter_stats(s, primary):
    before = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"]).json()
    code = primary["user"]["referral_code"]
    invitee_email = f"refstat+{TS}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": invitee_email, "password": "abcdef", "name": "RefStat", "ref": code
    })
    assert r.status_code == 200
    after = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"]).json()
    assert after["friends_joined"] == before["friends_joined"] + 1
    assert after["bonus_matches"] == before["bonus_matches"] + 3


# ---- Share kinds story / square + increments shares ----
def test_share_kind_story_accepted_and_increments(s, primary):
    before = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"]).json()["shares"]
    r = s.post(f"{BASE_URL}/api/share", json={"kind": "story"}, headers=primary["headers"])
    assert r.status_code == 200, r.text
    after = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"]).json()["shares"]
    assert after == before + 1


def test_share_kind_square_accepted_and_increments(s, primary):
    before = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"]).json()["shares"]
    r = s.post(f"{BASE_URL}/api/share", json={"kind": "square"}, headers=primary["headers"])
    assert r.status_code == 200, r.text
    after = s.get(f"{BASE_URL}/api/me/stats", headers=primary["headers"]).json()["shares"]
    assert after == before + 1


def test_share_invalid_kind_rejected(s, primary):
    r = s.post(f"{BASE_URL}/api/share", json={"kind": "bogus_kind"}, headers=primary["headers"])
    assert r.status_code == 422


# ---- Compare endpoints auth ----
def test_compare_endpoints_require_auth(s):
    r = s.post(f"{BASE_URL}/api/compare", json={"title": "x"})
    assert r.status_code == 401
    r = s.post(f"{BASE_URL}/api/compare/anything/join")
    assert r.status_code == 401
    r = s.get(f"{BASE_URL}/api/compare/anything")
    assert r.status_code == 401


# ---- Create compare room ----
def test_create_compare_returns_id_host_is_participant(s, primary):
    r = s.post(f"{BASE_URL}/api/compare", json={"title": "test room"}, headers=primary["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert "id" in body and body["id"]
    # fetch room to verify host is in participants
    r2 = s.get(f"{BASE_URL}/api/compare/{body['id']}", headers=primary["headers"])
    assert r2.status_code == 200
    room = r2.json()
    primary_id = primary["user"]["id"]
    participant_ids = [p["id"] for p in room["participants"]]
    assert primary_id in participant_ids
    assert room["title"] == "test room"


# ---- Join compare ----
def test_join_compare_adds_user_idempotently(s, primary, second):
    r = s.post(f"{BASE_URL}/api/compare", json={"title": "join-test"}, headers=primary["headers"])
    room_id = r.json()["id"]
    # second joins
    r1 = s.post(f"{BASE_URL}/api/compare/{room_id}/join", headers=second["headers"])
    assert r1.status_code == 200
    # join twice => idempotent
    r2 = s.post(f"{BASE_URL}/api/compare/{room_id}/join", headers=second["headers"])
    assert r2.status_code == 200
    # verify count is 2
    r3 = s.get(f"{BASE_URL}/api/compare/{room_id}", headers=primary["headers"])
    assert r3.status_code == 200
    data = r3.json()
    assert data["participant_count"] == 2
    pids = [p["id"] for p in data["participants"]]
    assert primary["user"]["id"] in pids
    assert second["user"]["id"] in pids


def test_join_missing_room_returns_404(s, primary):
    r = s.post(f"{BASE_URL}/api/compare/does-not-exist-zzz/join", headers=primary["headers"])
    assert r.status_code == 404


# ---- Get compare with auto-join + photo stripping + pairs ----
def test_get_compare_auto_joins_viewer(s, primary, third):
    # primary creates
    r = s.post(f"{BASE_URL}/api/compare", json={"title": "auto-join"}, headers=primary["headers"])
    room_id = r.json()["id"]
    # third views (not yet joined)
    r2 = s.get(f"{BASE_URL}/api/compare/{room_id}", headers=third["headers"])
    assert r2.status_code == 200
    data = r2.json()
    pids = [p["id"] for p in data["participants"]]
    assert third["user"]["id"] in pids
    assert data["participant_count"] >= 2


def test_get_compare_single_participant_no_pairs(s):
    s2 = requests.Session()
    solo = _signup(s2, "solo")
    _onboard(s2, solo["headers"], "solo", "woman")
    r = s2.post(f"{BASE_URL}/api/compare", json={"title": "solo-room"}, headers=solo["headers"])
    room_id = r.json()["id"]
    r2 = s2.get(f"{BASE_URL}/api/compare/{room_id}", headers=solo["headers"])
    assert r2.status_code == 200
    data = r2.json()
    assert data["participant_count"] == 1
    assert data["pairs"] == []
    assert data["strongest_twin"] is None
    # photo stripping check
    for p in data["participants"]:
        # public_profile keys only
        assert "password_hash" not in p
        assert "embedding" not in p
        assert "email" not in p


def test_get_compare_three_participants_pair_count_and_ordering(s, primary, second, third):
    # primary creates
    r = s.post(f"{BASE_URL}/api/compare", json={"title": "three-room"}, headers=primary["headers"])
    room_id = r.json()["id"]
    # second and third join
    s.post(f"{BASE_URL}/api/compare/{room_id}/join", headers=second["headers"])
    s.post(f"{BASE_URL}/api/compare/{room_id}/join", headers=third["headers"])
    r2 = s.get(f"{BASE_URL}/api/compare/{room_id}", headers=primary["headers"])
    assert r2.status_code == 200
    data = r2.json()
    assert data["participant_count"] == 3
    pairs = data["pairs"]
    # C(3,2) = 3
    assert len(pairs) == 3
    scores = [p["score"] for p in pairs]
    assert scores == sorted(scores, reverse=True)
    assert data["strongest_twin"]["score"] == max(scores)
    assert data["chaos_contrast"]["score"] == min(scores)
    # required nested fields
    for p in pairs:
        assert "a" in p and "b" in p and "score" in p
        assert "id" in p["a"] and "id" in p["b"]


def test_get_compare_missing_room_returns_404(s, primary):
    r = s.get(f"{BASE_URL}/api/compare/does-not-exist-zzz", headers=primary["headers"])
    assert r.status_code == 404

"""DoppelCrush backend API tests."""
import os
import time
import math
import hashlib
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "http://localhost:8001"
# Read from frontend .env if not set
if "REACT_APP_BACKEND_URL" not in os.environ:
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


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def primary_user(s):
    email = f"pookie+{TS}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "crushme123", "name": "Pookie"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    return {"email": email, "password": "crushme123", "token": data["token"], "user": data["user"]}


@pytest.fixture(scope="module")
def auth_headers(primary_user):
    return {"Authorization": f"Bearer {primary_user['token']}"}


# ---- Health ----
def test_root_health(s):
    r = s.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    assert r.json().get("ok") is True


# ---- Auth ----
def test_signup_returns_token_and_referral(primary_user):
    u = primary_user["user"]
    assert "id" in u
    assert u["email"] == primary_user["email"]
    assert u["referral_code"] and len(u["referral_code"]) >= 4
    assert "password_hash" not in u
    assert primary_user["token"]


def test_login_success(s, primary_user):
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": primary_user["email"], "password": primary_user["password"]})
    assert r.status_code == 200
    data = r.json()
    assert data["token"]
    assert data["user"]["email"] == primary_user["email"]
    assert "password_hash" not in data["user"]


def test_login_wrong_password(s, primary_user):
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": primary_user["email"], "password": "wrong"})
    assert r.status_code == 401


def test_auth_me_returns_user_without_secrets(s, auth_headers, primary_user):
    r = s.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    u = r.json()
    assert u["email"] == primary_user["email"]
    assert "password_hash" not in u
    assert "embedding" not in u


def test_auth_me_requires_token(s):
    r = s.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 401


def test_endpoints_require_auth(s):
    for path in ["/api/discover", "/api/matches"]:
        r = s.get(f"{BASE_URL}{path}")
        assert r.status_code == 401, path
    r = s.post(f"{BASE_URL}/api/onboarding", json={})
    assert r.status_code == 401
    r = s.post(f"{BASE_URL}/api/swipe", json={"target_id": "x", "direction": "like"})
    assert r.status_code == 401
    r = s.post(f"{BASE_URL}/api/share", json={"kind": "invite"})
    assert r.status_code == 401


# ---- Onboarding ----
def test_onboarding_sets_user_fields(s, auth_headers):
    body = {
        "age": 22, "gender": "woman", "looking_for": "men", "mode": "doppel",
        "bio": "test bio", "location": "NYC",
        "photo_url": "https://example.com/a.jpg",
        "embedding": _embedding("pookie_user"),
    }
    r = s.post(f"{BASE_URL}/api/onboarding", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["onboarding_complete"] is True
    assert u["age"] == 22
    assert u["gender"] == "woman"
    assert u["looking_for"] == "men"
    assert u["mode"] == "doppel"
    assert "embedding" not in u
    assert "password_hash" not in u


def test_patch_mode_toggles(s, auth_headers):
    r = s.patch(f"{BASE_URL}/api/me/mode", json={"mode": "chaos"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["mode"] == "chaos"
    r = s.patch(f"{BASE_URL}/api/me/mode", json={"mode": "doppel"}, headers=auth_headers)
    assert r.json()["mode"] == "doppel"
    r = s.patch(f"{BASE_URL}/api/me/mode", json={"mode": "bogus"}, headers=auth_headers)
    assert r.status_code == 400


# ---- Discover ----
def test_discover_doppel_ranking(s, auth_headers):
    r = s.get(f"{BASE_URL}/api/discover?mode=doppel", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "doppel"
    results = data["results"]
    # looking_for=men so only men
    assert len(results) > 0
    assert all(p["gender"] == "man" for p in results)
    assert len(results) <= 12
    scores = [p["score"] for p in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s_ <= 100 for s_ in scores)


def test_discover_chaos_ordering(s, auth_headers):
    r = s.get(f"{BASE_URL}/api/discover?mode=chaos", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "chaos"
    results = data["results"]
    assert len(results) > 0
    scores = [p["score"] for p in results]
    # chaos display = 100-pct, sorted by lowest sim first => highest display first
    assert scores == sorted(scores, reverse=True)


def test_looking_for_filter_everyone(s, primary_user):
    # Create a new user with looking_for=everyone
    email = f"every+{TS}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "abcdef", "name": "Every"
    })
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    s.post(f"{BASE_URL}/api/onboarding", json={
        "age": 25, "gender": "nonbinary", "looking_for": "everyone", "mode": "doppel",
        "photo_url": "https://x/y.jpg", "embedding": _embedding("every")
    }, headers=h)
    r = s.get(f"{BASE_URL}/api/discover", headers=h)
    assert r.status_code == 200
    genders = {p["gender"] for p in r.json()["results"]}
    assert "man" in genders and "woman" in genders


# ---- Swipe ----
def test_swipe_pass_no_match(s, auth_headers):
    r = s.get(f"{BASE_URL}/api/discover?mode=doppel", headers=auth_headers)
    target = r.json()["results"][0]
    r = s.post(f"{BASE_URL}/api/swipe",
               json={"target_id": target["id"], "direction": "pass"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["match"] is False


def test_swipe_like_seed_auto_match_and_excluded(s, auth_headers):
    r = s.get(f"{BASE_URL}/api/discover?mode=doppel", headers=auth_headers)
    results_before = r.json()["results"]
    target = results_before[0]
    target_id = target["id"]
    r = s.post(f"{BASE_URL}/api/swipe",
               json={"target_id": target_id, "direction": "like"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["match"] is True
    # discover should exclude already-swiped
    r = s.get(f"{BASE_URL}/api/discover?mode=doppel", headers=auth_headers)
    after_ids = {p["id"] for p in r.json()["results"]}
    assert target_id not in after_ids


def test_matches_list(s, auth_headers):
    r = s.get(f"{BASE_URL}/api/matches", headers=auth_headers)
    assert r.status_code == 200
    matches = r.json()
    assert isinstance(matches, list)
    assert len(matches) >= 1
    assert "profile" in matches[0]
    assert "id" in matches[0]["profile"]


# ---- Share / Referral ----
def test_share_increments_counter(s, auth_headers, primary_user):
    me_before = s.get(f"{BASE_URL}/api/auth/me", headers=auth_headers).json()
    before = me_before.get("extra_daily_matches", 0)
    r = s.post(f"{BASE_URL}/api/share", json={"kind": "reveal_card"}, headers=auth_headers)
    assert r.status_code == 200
    me_after = s.get(f"{BASE_URL}/api/auth/me", headers=auth_headers).json()
    assert me_after["extra_daily_matches"] == before + 1


def test_referral_valid_and_invalid(s, primary_user):
    code = primary_user["user"]["referral_code"]
    r = s.get(f"{BASE_URL}/api/referral/{code}")
    assert r.status_code == 200
    assert r.json()["valid"] is True
    r = s.get(f"{BASE_URL}/api/referral/NOPE_INVALID_XYZ")
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_signup_with_ref_increments_inviter(s, primary_user, auth_headers):
    before = s.get(f"{BASE_URL}/api/auth/me", headers=auth_headers).json()["extra_daily_matches"]
    code = primary_user["user"]["referral_code"]
    email = f"invitee+{TS}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "abcdef", "name": "Invitee", "ref": code
    })
    assert r.status_code == 200
    after = s.get(f"{BASE_URL}/api/auth/me", headers=auth_headers).json()["extra_daily_matches"]
    assert after == before + 3

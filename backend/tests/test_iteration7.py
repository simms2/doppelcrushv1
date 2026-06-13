"""Iteration 7 tests — post-refactor regression + new OG / twin-page / share kinds /
rate limiting / lifespan-seeded users.

Covers:
- (a) Backwards compat for all previously-working endpoints after the modularisation
  refactor (server.py thin shell + routers/*.py).
- (b) New GET /api/og/twin/{user_id}.png — 1200x630 dynamic PNG.
- (c) New GET /api/share/twin-page/{user_id} — crawler HTML w/ OG + twitter tags.
- (d) Extended ShareEventIn literal: invite_card, whatsapp, x, instagram, threads.
- (e) Rate limiting on /api/share/twin/{id} (30/60s) and /api/og/twin/{id}.png (60/60s).
- (f) Lifespan handler — seed users present after startup; lola@seed.doppelcrush resolves.
"""
from __future__ import annotations

import io
import os
import struct
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://facial-vibes.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ────────────────────────────── helpers ──────────────────────────────────
def _email(tag: str) -> str:
    # NOTE: server lower-cases emails, so keep lowercase to allow round-trip compare.
    return f"test_iter7_{tag}_{uuid.uuid4().hex[:8]}@example.com"


def _signup(payload):
    return requests.post(f"{API}/auth/signup", json=payload, timeout=30)


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _discover_cards(token, mode="doppel"):
    """Discover endpoint may return either [cards] (legacy) or {mode, results}."""
    r = requests.get(f"{API}/discover?mode={mode}", headers=_hdr(token), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return []


def _onboard(token, photo_url="https://example.com/p.jpg", age=27, mode="doppel"):
    body = {
        "age": age,
        "gender": "woman",
        "looking_for": "everyone",
        "mode": mode,
        "bio": "Iter7 bio",
        "location": "Brooklyn",
        "photo_url": photo_url,
        "embedding": [0.1] * 128,
        "quality_score": 0.8,
    }
    return requests.post(f"{API}/onboarding", json=body, headers=_hdr(token), timeout=30)


# ─────────────────────────── shared fixtures ────────────────────────────
@pytest.fixture(scope="module")
def onboarded_user():
    em = _email("primary")
    r = _signup({"email": em, "password": "passw0rd!", "name": "PrimaryUser"})
    assert r.status_code == 200, r.text
    data = r.json()
    ob = _onboard(data["token"], photo_url="https://example.com/twin.jpg", age=28)
    assert ob.status_code == 200, ob.text
    return {"token": data["token"], "user": data["user"], "email": em,
            "referral_code": data["user"]["referral_code"]}


@pytest.fixture(scope="module")
def second_user():
    em = _email("second")
    r = _signup({"email": em, "password": "passw0rd!", "name": "SecondUser"})
    assert r.status_code == 200, r.text
    data = r.json()
    ob = _onboard(data["token"], photo_url="https://example.com/twin2.jpg", age=27)
    assert ob.status_code == 200, ob.text
    return {"token": data["token"], "user": data["user"], "email": em}


@pytest.fixture(scope="module")
def seed_user_id(onboarded_user):
    """Pull a seed user id from /api/discover."""
    cards = _discover_cards(onboarded_user["token"], mode="doppel")
    assert len(cards) > 0, "discover returned no seed candidates"
    # Prefer any with a photo_url that is NOT one of our test users
    candidates = [c for c in cards
                  if c.get("photo_url") and c.get("id") != onboarded_user["user"]["id"]]
    assert candidates, "No seed user with photo_url in discover"
    return candidates[0]["id"]


# ════════════════════════════════════════════════════════════════════════
# (f) Lifespan seed data
# ════════════════════════════════════════════════════════════════════════
class TestLifespanSeed:
    def test_seed_users_visible_via_discover(self, onboarded_user):
        cards = _discover_cards(onboarded_user["token"], mode="doppel")
        assert len(cards) >= 1, "Lifespan should have seeded users"

    def test_seed_users_have_names(self, onboarded_user):
        cards = _discover_cards(onboarded_user["token"], mode="doppel")
        names = {c.get("name") for c in cards if c.get("name")}
        assert names, "No named seed profiles returned from discover"
        # The 12 seeded names include at least one of these recognisable handles
        expected = {"Lola", "Kai", "Ivy", "Nova", "Ezra", "Juno",
                    "Milo", "Remy", "Theo", "Sasha", "Amara", "Rio"}
        assert names & expected, f"None of the known seed names found. Got: {names}"


# ════════════════════════════════════════════════════════════════════════
# (a) Regression — all previously-working endpoints still respond
# ════════════════════════════════════════════════════════════════════════
class TestRegressionAuth:
    def test_signup(self):
        em = _email("regsignup")
        r = _signup({"email": em, "password": "passw0rd!", "name": "RegUser"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body and "user" in body
        assert body["user"]["email"] == em

    def test_login(self, onboarded_user):
        r = requests.post(f"{API}/auth/login",
                          json={"email": onboarded_user["email"], "password": "passw0rd!"},
                          timeout=20)
        assert r.status_code == 200, r.text
        assert "token" in r.json()

    def test_me(self, onboarded_user):
        r = requests.get(f"{API}/auth/me", headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 200
        assert r.json()["email"] == onboarded_user["email"]


class TestRegressionMatching:
    def test_discover(self, onboarded_user):
        cards = _discover_cards(onboarded_user["token"], mode="doppel")
        assert isinstance(cards, list)

    def test_swipe_like_creates_match_with_seed(self, onboarded_user, seed_user_id):
        r = requests.post(f"{API}/swipe",
                          json={"target_id": seed_user_id, "direction": "like"},
                          headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 200, r.text

    def test_matches_list_and_detail(self, onboarded_user):
        r = requests.get(f"{API}/matches", headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 200
        matches = r.json()
        assert isinstance(matches, list)
        if matches:
            mid = matches[0]["id"]
            r2 = requests.get(f"{API}/matches/{mid}",
                              headers=_hdr(onboarded_user["token"]), timeout=20)
            assert r2.status_code == 200
            assert r2.json()["id"] == mid

    def test_messages_post_and_get(self, onboarded_user):
        r = requests.get(f"{API}/matches", headers=_hdr(onboarded_user["token"]), timeout=20)
        matches = r.json()
        if not matches:
            pytest.skip("No matches available to test messages")
        mid = matches[0]["id"]
        post = requests.post(f"{API}/matches/{mid}/messages",
                             json={"body": "hello from iter7"},
                             headers=_hdr(onboarded_user["token"]), timeout=20)
        assert post.status_code == 200, post.text
        getr = requests.get(f"{API}/matches/{mid}/messages",
                            headers=_hdr(onboarded_user["token"]), timeout=20)
        assert getr.status_code == 200
        bodies = [m.get("body") for m in getr.json()]
        assert "hello from iter7" in bodies


class TestRegressionMeStats:
    def test_me_stats(self, onboarded_user):
        r = requests.get(f"{API}/me/stats", headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 200
        data = r.json()
        for k in ("friends_joined", "bonus_matches"):
            assert k in data

    def test_me_unread(self, onboarded_user):
        r = requests.get(f"{API}/me/unread", headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestRegressionReferral:
    def test_referral_valid(self, onboarded_user):
        r = requests.get(f"{API}/referral/{onboarded_user['referral_code']}", timeout=20)
        assert r.status_code == 200
        assert r.json()["valid"] is True

    def test_referral_invalid(self):
        r = requests.get(f"{API}/referral/NOPE_{uuid.uuid4().hex[:6]}", timeout=20)
        assert r.status_code == 200
        assert r.json() == {"valid": False}


class TestRegressionCompare:
    def test_create_and_get_compare(self, onboarded_user):
        create = requests.post(f"{API}/compare",
                               json={"title": "iter7 room"},
                               headers=_hdr(onboarded_user["token"]), timeout=20)
        assert create.status_code == 200, create.text
        rid = create.json()["id"]
        getr = requests.get(f"{API}/compare/{rid}",
                            headers=_hdr(onboarded_user["token"]), timeout=20)
        assert getr.status_code == 200
        assert getr.json()["id"] == rid


# ════════════════════════════════════════════════════════════════════════
# (d) Extended /api/share kinds
# ════════════════════════════════════════════════════════════════════════
class TestShareKinds:
    @pytest.mark.parametrize("kind", ["whatsapp", "x", "instagram", "threads", "invite_card"])
    def test_new_share_kinds_accepted(self, onboarded_user, kind):
        pre = requests.get(f"{API}/auth/me",
                           headers=_hdr(onboarded_user["token"]), timeout=20).json()
        pre_extra = pre.get("extra_daily_matches", 0)
        r = requests.post(f"{API}/share",
                          json={"kind": kind},
                          headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 200, f"kind={kind} -> {r.status_code}: {r.text}"
        assert r.json() == {"ok": True}
        post = requests.get(f"{API}/auth/me",
                            headers=_hdr(onboarded_user["token"]), timeout=20).json()
        assert post.get("extra_daily_matches", 0) == pre_extra + 1, \
            f"extra_daily_matches not incremented for kind={kind}"

    def test_legacy_share_kinds_still_accepted(self, onboarded_user):
        for kind in ("reveal_card", "invite", "match_card", "story", "square"):
            r = requests.post(f"{API}/share", json={"kind": kind},
                              headers=_hdr(onboarded_user["token"]), timeout=20)
            assert r.status_code == 200, f"legacy kind={kind} -> {r.status_code}"

    def test_invalid_share_kind_422(self, onboarded_user):
        r = requests.post(f"{API}/share",
                          json={"kind": "not_a_kind"},
                          headers=_hdr(onboarded_user["token"]), timeout=20)
        assert r.status_code == 422, r.text


# ════════════════════════════════════════════════════════════════════════
# (b) GET /api/og/twin/{user_id}.png
# ════════════════════════════════════════════════════════════════════════
def _png_dimensions(data: bytes):
    """Return (width, height) of a PNG byte stream."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "Not a PNG signature"
    # IHDR is the first chunk after 8-byte sig: 4-byte length, 4-byte type, then data
    w, h = struct.unpack(">II", data[16:24])
    return w, h


class TestOgTwinImage:
    def test_returns_png_for_seed(self, seed_user_id):
        r = requests.get(f"{API}/og/twin/{seed_user_id}.png", timeout=30)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image/png")
        assert r.headers.get("cache-control"), "Missing Cache-Control header"
        assert len(r.content) > 1000, "PNG suspiciously small"
        w, h = _png_dimensions(r.content)
        assert (w, h) == (1200, 630), f"Expected 1200x630, got {w}x{h}"

    def test_returns_fallback_png_for_unknown(self):
        """Unknown users get a generic brand PNG (200) so unfurlers don't cache 404."""
        r = requests.get(f"{API}/og/twin/does-not-exist-{uuid.uuid4()}.png", timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type") == "image/png"
        w, h = _png_dimensions(r.content)
        assert (w, h) == (1200, 630)

    def test_returns_fallback_png_for_non_onboarded(self):
        em = _email("nonob_og")
        s = _signup({"email": em, "password": "passw0rd!", "name": "NotOB"})
        assert s.status_code == 200
        uid = s.json()["user"]["id"]
        r = requests.get(f"{API}/og/twin/{uid}.png", timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type") == "image/png"


# ════════════════════════════════════════════════════════════════════════
# (c) GET /api/share/twin-page/{user_id}
# ════════════════════════════════════════════════════════════════════════
class TestTwinSharePage:
    def test_returns_html_with_og_tags_for_real_user(self, seed_user_id):
        r = requests.get(f"{API}/share/twin-page/{seed_user_id}", timeout=20)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "").lower()
        assert "text/html" in ct, ct
        html = r.text
        for tag in ('property="og:title"', 'property="og:description"',
                    'property="og:image"', 'property="og:url"',
                    'name="twitter:card"'):
            assert tag in html, f"Missing meta tag: {tag}"
        # og:image must point at our OG image route
        assert f"/api/og/twin/{seed_user_id}.png" in html

    def test_returns_html_with_generic_fallback_for_unknown_user(self):
        fake = f"does-not-exist-{uuid.uuid4()}"
        r = requests.get(f"{API}/share/twin-page/{fake}", timeout=20)
        # Endpoint NEVER 404s for the page itself per the spec
        assert r.status_code == 200
        html = r.text
        assert 'property="og:title"' in html
        assert 'property="og:image"' in html
        # Should use generic DoppelCrush copy
        assert "DoppelCrush" in html

    def test_og_url_uses_forwarded_host(self, seed_user_id):
        """When called via the public ingress, og:url + og:image should reflect
        the public https hostname (x-forwarded-host honored)."""
        r = requests.get(f"{API}/share/twin-page/{seed_user_id}", timeout=20)
        html = r.text
        # The public ingress should inject x-forwarded-host; assert https + public domain
        from urllib.parse import urlparse
        public_host = urlparse(BASE_URL).netloc
        assert f"https://{public_host}/your-twin/{seed_user_id}" in html, \
            f"og:url not using public host. BASE_URL={BASE_URL}; html head:\n{html[:1200]}"
        assert f"https://{public_host}/api/og/twin/{seed_user_id}.png" in html


# ════════════════════════════════════════════════════════════════════════
# (e) Rate limiting
# ════════════════════════════════════════════════════════════════════════
class TestRateLimits:
    """In-process sliding-window limiter is keyed on client IP. From a single
    external client we expect to trip the limit deterministically."""

    def test_twin_teaser_30_per_min(self, seed_user_id):
        # Fire 35 calls; expect at least one 429 in the last few
        session = requests.Session()
        statuses = []
        url = f"{API}/share/twin/{seed_user_id}"
        for _ in range(35):
            try:
                statuses.append(session.get(url, timeout=15).status_code)
            except requests.RequestException as e:
                statuses.append(f"err:{e}")
        ok = sum(1 for s in statuses if s == 200)
        too_many = sum(1 for s in statuses if s == 429)
        assert too_many >= 1, f"Expected at least one 429 on twin teaser, got: {statuses}"
        # 200s should not exceed 30 in the window
        assert ok <= 30, f"Got {ok} 200s — exceeded 30/min cap. statuses={statuses}"

    def test_og_image_60_per_min(self, seed_user_id):
        # Wait for the twinpage / ogimg keys to not collide with the above test.
        # Different keys (twin vs ogimg) — but be safe.
        session = requests.Session()
        statuses = []
        url = f"{API}/og/twin/{seed_user_id}.png"
        for _ in range(65):
            try:
                statuses.append(session.get(url, timeout=20).status_code)
            except requests.RequestException as e:
                statuses.append(f"err:{e}")
        ok = sum(1 for s in statuses if s == 200)
        too_many = sum(1 for s in statuses if s == 429)
        assert too_many >= 1, f"Expected at least one 429 on og image, got: {statuses}"
        assert ok <= 60, f"Got {ok} 200s — exceeded 60/min cap. statuses={statuses}"

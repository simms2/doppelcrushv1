# DoppelCrush — PRD

## Problem statement
Playful selfie-first dating / social discovery app. Two modes:
- **Doppel** — find people with similar facial structure ("twin energy")
- **Chaos** — discover deliberately different, unexpected matches
Brand: glossy, playful, social, viral, confident, safe. Never creepy.

## Personas
- Gen-Z singles (18–25) who want a low-effort, share-driven flirt loop
- Group-chat friends who want to play the "who looks alike?" game

## Tech
- Backend: FastAPI + MongoDB, JWT auth (bcrypt + PyJWT)
- Face matching: face-api.js in browser → 128-dim descriptor → backend cosine ranking
- Frontend: React 19 + Tailwind + shadcn UI + framer-motion
- Routes prefixed `/api`; env: `MONGO_URL`, `JWT_SECRET`, `REACT_APP_BACKEND_URL`

## Implemented (Feb 2026)
- ✅ Homepage matching the puffy sticker mockup (Fredoka + Quicksand, gradient `DoppelCrush` text, kawaii heart, live preview window)
- ✅ JWT signup/login/me with referral codes
- ✅ Multi-step onboarding (selfie + face-api embedding, age 18+, gender, looking_for, mode)
- ✅ Discover swipe feed with real cosine ranking (Doppel vs Chaos)
- ✅ Like/Pass swipe; auto-match on seed profiles; matches list
- ✅ Match reveal page with HTML5-canvas branded share card (square + story formats)
- ✅ Static pages: How it works / Safety / FAQ
- ✅ Viral growth system
  - `/invite` page — code, copy, WhatsApp / X / Instagram / Threads / native share, fun PNG card download (Post 1:1 + Story 9:16 formats toggle)
  - `/compare` group challenge rooms — strongest twin pair, chaos contrast, funniest mismatch
  - `/api/me/stats`, `/api/compare`, `/api/compare/{id}/join`, `/api/compare/{id}`
  - Share kinds: reveal_card, invite, invite_card, instagram, threads, whatsapp, x, match_card, story, square (+1 bonus per share)
- ✅ Bold meme-y canvas-rendered share card with two formats (1080x1080 + 1080x1920 story) auto-downloaded for Instagram, copied caption flow
- ✅ Dynamic Open Graph image generation
  - `GET /api/og/twin/{user_id}.png` — server-side rendered 1200x630 PNG (Pillow) with selfie circle, headline, code badge — returns 200 fallback PNG even for unknown IDs so unfurlers don't cache 404s
  - `GET /api/share/twin-page/{user_id}` — crawler-friendly HTML with og:title/description/image/url + twitter:card meta, honours x-forwarded-proto/host so absolute URLs are always public https
  - Profile page now shares the twin-page URL so iMessage/WhatsApp/Slack/Twitter unfurl with a rich preview
- ✅ Backend refactor: `server.py` reduced from 1100 → ~230 lines, split into `routers/{auth,match,chat,files,viral}.py` + `deps.py` + `models.py`
- ✅ Migrated to FastAPI `@asynccontextmanager lifespan` (no more deprecated on_event)
- ✅ In-process sliding-window rate limiter on public twin endpoints (30/min on teaser, 60/min on og + share-page)
- ✅ Header logo now routes to homepage (/) instead of /discover
- ✅ Backend tests: 118 passing (iterations 1–7), 1 skipped, 0 failed

## Backlog (P0/P1)
- P0: Real chat MVP between matched users (Messages page is a stub list)
- P0: Persisted selfie hosting (currently photo_url is a base64 data URL stored on the user document; switch to object storage)
- P1: Forgot-password + email verification
- P1: Daily match limit + boost economy (extra_daily_matches counter exists, not enforced yet)
- P1: Profile edit page
- P2: Push/web notifications on match
- P2: Mobile native share fallbacks for desktop
- P2: Friends Compare leaderboard archive

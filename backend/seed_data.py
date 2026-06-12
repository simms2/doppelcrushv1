"""Seed profiles for DoppelCrush MVP discover feed.

Each profile has a deterministic 128-dim mock embedding so cosine
similarity ranking against a real user's face-api.js descriptor still
produces stable Doppel / Chaos orderings.
"""
from __future__ import annotations

import hashlib
import math
from typing import List


def _embed_from_seed(seed: str, dim: int = 128) -> List[float]:
    """Deterministic pseudo-embedding from a string seed."""
    vec: List[float] = []
    counter = 0
    while len(vec) < dim:
        h = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        for b in h:
            # map 0..255 -> -1..1
            vec.append((b / 127.5) - 1.0)
            if len(vec) >= dim:
                break
        counter += 1
    # L2 normalise
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


SEED_PROFILES = [
    {
        "username": "lola",
        "name": "Lola",
        "age": 19,
        "gender": "woman",
        "bio": "Cute. Familiar. Elite taste.",
        "photo_url": "https://images.unsplash.com/photo-1557002665-c552e1832483?w=600&q=80",
        "location": "Brooklyn",
    },
    {
        "username": "kai",
        "name": "Kai",
        "age": 20,
        "gender": "man",
        "bio": "A total switch-up. Still a yes.",
        "photo_url": "https://images.unsplash.com/photo-1647593782884-1a6779139eb5?w=600&q=80",
        "location": "Los Angeles",
    },
    {
        "username": "ivy",
        "name": "Ivy",
        "age": 18,
        "gender": "woman",
        "bio": "Same vibe. Same face card energy.",
        "photo_url": "https://images.unsplash.com/photo-1713812956759-371b4e8fc468?w=600&q=80",
        "location": "Austin",
    },
    {
        "username": "nova",
        "name": "Nova",
        "age": 22,
        "gender": "woman",
        "bio": "Soft launch energy ✿",
        "photo_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=600&q=80",
        "location": "Miami",
    },
    {
        "username": "ezra",
        "name": "Ezra",
        "age": 23,
        "gender": "man",
        "bio": "Coffee shop poet, terrible texter.",
        "photo_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=600&q=80",
        "location": "Portland",
    },
    {
        "username": "juno",
        "name": "Juno",
        "age": 21,
        "gender": "woman",
        "bio": "Twin energy, plot twist heart.",
        "photo_url": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=600&q=80",
        "location": "Chicago",
    },
    {
        "username": "milo",
        "name": "Milo",
        "age": 24,
        "gender": "man",
        "bio": "I look chaotic. I am chaotic.",
        "photo_url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=600&q=80",
        "location": "Berlin",
    },
    {
        "username": "remy",
        "name": "Remy",
        "age": 20,
        "gender": "woman",
        "bio": "Aux cord defender. Late reply queen.",
        "photo_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&q=80",
        "location": "Toronto",
    },
    {
        "username": "theo",
        "name": "Theo",
        "age": 25,
        "gender": "man",
        "bio": "Soft boy with strong opinions on pasta.",
        "photo_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&q=80",
        "location": "London",
    },
    {
        "username": "sasha",
        "name": "Sasha",
        "age": 22,
        "gender": "nonbinary",
        "bio": "Chaos-coded. Doppel-curious.",
        "photo_url": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=600&q=80",
        "location": "Berlin",
    },
    {
        "username": "amara",
        "name": "Amara",
        "age": 21,
        "gender": "woman",
        "bio": "Looking for someone with the same face card.",
        "photo_url": "https://images.unsplash.com/photo-1554151228-14d9def656e4?w=600&q=80",
        "location": "Lagos",
    },
    {
        "username": "rio",
        "name": "Rio",
        "age": 23,
        "gender": "man",
        "bio": "Plot twist energy. Will pick the weird option.",
        "photo_url": "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=600&q=80",
        "location": "Mexico City",
    },
]


def get_seed_profiles_with_embeddings() -> list[dict]:
    out = []
    for p in SEED_PROFILES:
        out.append({**p, "embedding": _embed_from_seed(p["username"])})
    return out

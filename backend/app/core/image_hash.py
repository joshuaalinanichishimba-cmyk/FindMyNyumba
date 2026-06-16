"""
app/core/image_hash.py

Duplicate / reused-image detection.

WHY
---
The two highest-value fakes on a Zambian housing platform are (1) the same
stolen property photos pasted across many "listings", and (2) the same NRC or
selfie reused to open multiple "landlord" accounts. Both are caught by a
perceptual hash (pHash): unlike an exact checksum, it stays stable through
re-compression, light cropping and resizing, so it catches near-duplicates that
an MD5 would miss.

Pillow is already a dependency (see requirements.txt), so this needs NO new
package. We implement a 64-bit difference hash (dHash) ourselves — small, fast,
no libmagic, identical behaviour locally and on Render.

Two hashes are "similar" when their Hamming distance is small (default <= 10
bits out of 64). Exact reuse gives distance 0.

USAGE
-----
    from app.core.image_hash import phash_bytes, hamming_distance, is_duplicate

    h = phash_bytes(file_bytes)        # -> 16-char hex string, or None on failure
    if is_duplicate(h, existing_hash): ...

Cloudinary can also return a `phash` field on upload (pass phash=True); if you
prefer to offload the compute, store that instead — the comparison helpers here
work on any hex string of equal length.
"""
from __future__ import annotations

import io
from typing import Optional

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

HASH_SIZE = 8  # 8x8 grid -> 64-bit hash
DEFAULT_THRESHOLD = 10  # max Hamming distance to count as a match


def phash_bytes(data: bytes) -> Optional[str]:
    """
    Compute a 64-bit difference hash of an image, returned as 16 hex chars.
    Returns None if the bytes aren't a decodable image (never raises).
    """
    if Image is None or not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("L").resize(
            (HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS
        )
        pixels = list(img.getdata())
        # Compare each pixel to its right neighbour, row by row.
        bits = 0
        bit_index = 0
        for row in range(HASH_SIZE):
            for col in range(HASH_SIZE):
                left = pixels[row * (HASH_SIZE + 1) + col]
                right = pixels[row * (HASH_SIZE + 1) + col + 1]
                if left > right:
                    bits |= (1 << bit_index)
                bit_index += 1
        return f"{bits:016x}"
    except Exception:
        return None


def hamming_distance(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Number of differing bits between two hex hashes. None if not comparable."""
    if not a or not b or len(a) != len(b):
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


def is_duplicate(a: Optional[str], b: Optional[str],
                 threshold: int = DEFAULT_THRESHOLD) -> bool:
    """True when two hashes are within `threshold` bits (i.e. near-identical)."""
    d = hamming_distance(a, b)
    return d is not None and d <= threshold


def find_duplicates(target: Optional[str], candidates: list[tuple],
                    threshold: int = DEFAULT_THRESHOLD) -> list[tuple]:
    """
    Given a target hash and a list of (id, hash) candidates, return the subset
    that are near-duplicates of the target. Used to flag a freshly uploaded
    image against everything already on the platform.
    """
    if not target:
        return []
    out = []
    for cid, chash in candidates:
        if is_duplicate(target, chash, threshold):
            out.append((cid, chash))
    return out

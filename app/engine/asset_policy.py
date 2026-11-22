"""Shared exact-byte review policy primitives (stdlib only)."""
from __future__ import annotations

import hashlib
from pathlib import Path

MEMBERS = ("chorong", "bomi", "eunji", "namjoo", "hayoung")
BASIC_ACTIONS = ("idle", "walk", "cheer", "sleep")
# Canonical frame/ground-anchor pairs. Large frames require explicit consumer tags.
CANVAS_ANCHORS = {(256, 256): (128, 244), (384, 384): (192, 372),
                  (384, 416): (192, 372)}  # extra space below feet for hanging props
KNOWN_BLOCKED = {
    "shared/interactions_duo/duo_bomi_eunji_banter_standoff.png":
        "Observed birthday cake scene, not the declared banter; stray crop fragments.",
    "hayoung/situational_v6_3/hayoung_soccer_shoot.png":
        "Observed sleeping with sweet potato, not soccer; top-edge crop fragments.",
    "eunji/situational_v6_3/eunji_microphone_belt.png":
        "Observed guitar pose, not the declared microphone action.",
}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

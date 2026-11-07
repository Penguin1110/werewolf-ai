"""從發言中抽取「跳身分 / 報查驗」的結構化資訊。

LLM 可以直接在回應中給 claim 欄位；若沒有，就用簡單的關鍵字規則從文字中猜。
claim 格式：{"role": "seer", "checks": {"5": "wolf", "3": "good"}}
"""
from __future__ import annotations

import re
from typing import Optional

from .roles import ROLE_ALIASES

_WOLF = re.compile(r"(\d{1,2})\s*號[^，。,.!！？;；]{0,6}?(查殺|是狼|是一匹狼|狼人)")
_GOOD = re.compile(r"(\d{1,2})\s*號[^，。,.!！？;；]{0,6}?(金水|是好人|好人)")
_SELF = re.compile(r"我(?:是|就是|跳|才是|是真的?)\s*(?:真)?(預言家|预言家|女巫|獵人|猎人|守衛|守卫|村民|平民)")


def normalize_claim(claim) -> Optional[dict]:
    if not isinstance(claim, dict):
        return None
    role = claim.get("role")
    for key, aliases in ROLE_ALIASES.items():
        if role == key or role in aliases:
            role = key
            break
    else:
        role = None
    checks = {}
    raw = claim.get("checks") or {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                k = str(int(k))
            except (TypeError, ValueError):
                continue
            v = str(v).lower()
            if v in ("wolf", "werewolf", "狼", "狼人", "查殺", "bad"):
                checks[k] = "wolf"
            elif v in ("good", "好人", "金水", "human", "village"):
                checks[k] = "good"
    if not role and not checks:
        return None
    if checks and not role:
        role = "seer"
    return {"role": role, "checks": checks}


def extract_claim(text: str) -> Optional[dict]:
    if not text:
        return None
    m = _SELF.search(text)
    role = None
    if m:
        for key, aliases in ROLE_ALIASES.items():
            if m.group(1) in aliases:
                role = key
    checks = {}
    if role == "seer":
        for m in _WOLF.finditer(text):
            checks[str(int(m.group(1)))] = "wolf"
        for m in _GOOD.finditer(text):
            checks.setdefault(str(int(m.group(1))), "good")
    if not role:
        return None
    return {"role": role, "checks": checks}

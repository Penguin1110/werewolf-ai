"""策略 Skill 載入器。

一個 skill 就是 skills/ 底下的一個資料夾：

    skills/my_skill/
        SKILL.md       必填。前面是 YAML 風格的 frontmatter，後面是給 AI 看的策略說明。
        strategy.py    選填。用 Python 寫的硬規則 / 動態提示。

SKILL.md 內可以用「## 狼人」「## 預言家」等標題寫角色專屬策略，
AI 拿到哪個身分，就只會看到「通用段落 + 該身分段落」。
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from typing import Dict, List, Optional

from .roles import ROLE_ALIASES

GENERAL_HEADINGS = {"通用", "general", "共通", "全身分", "所有身分"}


class Skill:
    def __init__(self, skill_id: str, path: str):
        self.id = skill_id
        self.path = path
        self.meta: Dict[str, str] = {}
        self.general = ""
        self.by_role: Dict[str, str] = {}
        self.module = None
        self._load()

    # ------------------------------------------------------------------
    def _load(self):
        md_path = os.path.join(self.path, "SKILL.md")
        with open(md_path, encoding="utf-8") as f:
            text = f.read()
        body = text
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    self.meta[k.strip()] = v.strip().strip('"').strip("'")
            body = text[m.end():]
        general_parts: List[str] = []
        current: Optional[str] = None
        buf: List[str] = []

        def flush():
            content = "\n".join(buf).strip()
            if not content:
                return
            if current is None:
                general_parts.append(content)
            else:
                self.by_role[current] = (self.by_role.get(current, "") + "\n" + content).strip()

        for line in body.splitlines():
            h = re.match(r"^##\s+(.+?)\s*$", line)
            if h:
                flush()
                buf = []
                title = h.group(1).strip()
                current = "village" if ("好人" in title or "神職" in title) else None
                for key, aliases in ([] if current else ROLE_ALIASES.items()):
                    if any(a in title for a in aliases if len(a) > 1 or a == title):
                        current = key
                        break
                if current is None and title.lower() not in GENERAL_HEADINGS:
                    buf.append(line)  # 一般標題，保留為通用內容
                continue
            buf.append(line)
        flush()
        self.general = "\n\n".join(general_parts)

        py = os.path.join(self.path, "strategy.py")
        if os.path.exists(py):
            mod_name = f"ww_skill_{re.sub(r'[^0-9a-zA-Z_]', '_', self.id)}"
            spec = importlib.util.spec_from_file_location(mod_name, py)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            self.module = mod

    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self.meta.get("name", self.id)

    def prompt_for(self, role: str) -> str:
        parts = []
        if self.general:
            parts.append(self.general)
        if role != "werewolf" and self.by_role.get("village"):
            parts.append(self.by_role["village"])
        if self.by_role.get(role):
            parts.append(self.by_role[role])
        return "\n\n".join(parts).strip()

    def hook(self, name: str):
        return getattr(self.module, name, None) if self.module else None

    def info(self) -> dict:
        return {"id": self.id, "name": self.name, "author": self.meta.get("author", ""),
                "description": self.meta.get("description", ""), "has_code": self.module is not None,
                "roles": sorted(self.by_role.keys())}


def list_skills(skills_dir: str) -> List[Skill]:
    out = []
    for d in sorted(os.listdir(skills_dir)):
        full = os.path.join(skills_dir, d)
        if d.startswith((".", "_")) or not os.path.isdir(full):
            continue
        if not os.path.exists(os.path.join(full, "SKILL.md")):
            continue
        try:
            out.append(Skill(d, full))
        except Exception as e:  # 一個 skill 壞掉不要拖垮整個遊戲
            print(f"[skill] 載入 {d} 失敗：{e}")
    return out


_cache: Dict[str, Skill] = {}


def load_skill(skills_dir: str, skill_id: str, reload: bool = True) -> Skill:
    path = os.path.join(skills_dir, skill_id)
    if not os.path.exists(os.path.join(path, "SKILL.md")):
        raise FileNotFoundError(f"找不到 skill：{skill_id}（需要 {path}/SKILL.md）")
    if reload or skill_id not in _cache:
        _cache[skill_id] = Skill(skill_id, path)
    return _cache[skill_id]

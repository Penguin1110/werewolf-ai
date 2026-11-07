"""從設定檔建立玩家與遊戲。"""
from __future__ import annotations

import json
import os
import random
from typing import Callable, Optional

from .agents import LLMAgent, RuleAgent
from .game import Game
from .roles import BOARDS
from .skill import load_skill
from .llm import check_ready

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")
REPLAY_DIR = os.path.join(ROOT, "replays")


def load_config(path: Optional[str] = None) -> dict:
    path = path or os.path.join(ROOT, "config.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # 把共用的 openai 設定（base_url、金鑰、reasoning_effort…）套到每個 GPT 模型上
    shared = cfg.get("openai", {})
    for key, m in cfg.get("models", {}).items():
        if isinstance(m, dict) and m.get("provider", "openai") == "openai":
            cfg["models"][key] = {**shared, "provider": "openai", **m}
    return cfg


def _rule_style(skill) -> dict:
    style = {}
    if skill:
        for k, v in skill.meta.items():
            if k.startswith("rule_"):
                key = k[5:]
                try:
                    style[key] = float(v)
                except ValueError:
                    style[key] = v.lower() in ("true", "yes", "1")
    return style


def build_agent(spec: dict, models: dict, seed: int):
    skill = load_skill(SKILLS_DIR, spec["skill"]) if spec.get("skill") else None
    model_key = spec.get("model", "rule")
    cfg = models.get(model_key)
    if cfg is None:
        raise ValueError(f"config.json 的 models 裡沒有「{model_key}」")
    if cfg.get("provider", "rule") == "rule":
        agent = RuleAgent(seed=seed, style=_rule_style(skill), skill=skill)
    else:
        agent = LLMAgent(cfg, skill=skill, seed=seed)
    return agent, skill


def create_game(players: list, models: dict, board: str = "9", seed: Optional[int] = None,
                on_event: Optional[Callable] = None, rules: Optional[dict] = None) -> Game:
    if board not in BOARDS:
        raise ValueError(f"不支援的板子 {board}，可用：{list(BOARDS)}")
    n = len(BOARDS[board]["roles"])
    if len(players) < n:
        raise ValueError(f"{BOARDS[board]['name']} 需要 {n} 位玩家，設定裡只有 {len(players)} 位")
    players = players[:n]
    for p in players:
        if p.get("model", "rule") not in models:
            raise ValueError(f"config.json 的 models 裡沒有「{p.get('model')}」")
        check_ready(models[p.get("model", "rule")])
    seed = seed if seed is not None else random.randrange(1, 10 ** 9)
    specs = []
    for i, p in enumerate(players):
        agent, skill = build_agent(p, models, seed * 31 + i)
        specs.append({"name": p["name"], "agent": agent,
                      "skill": skill.name if skill else "（無）", "model": p.get("model", "rule")})
    counter = {"n": 0}

    def fallback():
        counter["n"] += 1
        return RuleAgent(seed=seed * 97 + counter["n"])

    return Game(specs, board=board, seed=seed, on_event=on_event, rules=rules, fallback_factory=fallback)


def save_replay(game: Game, meta: Optional[dict] = None) -> str:
    import time
    os.makedirs(REPLAY_DIR, exist_ok=True)
    name = time.strftime("%Y%m%d-%H%M%S") + f"_{game.board}p_{game.seed}.json"
    path = os.path.join(REPLAY_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(game.replay(meta), f, ensure_ascii=False)
    return path

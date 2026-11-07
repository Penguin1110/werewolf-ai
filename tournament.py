#!/usr/bin/env python3
"""策略擂台：連續跑很多局，統計每個 skill 的勝率。

    python tournament.py --games 50                 # 用 config.json 的玩家，跑 50 局
    python tournament.py --games 20 --board 12 --save-replays
    python tournament.py --games 30 --model rule    # 全部強制用某個模型，只比較 skill 本身

每局都會重新隨機分配身分（seed 不同），所以每個 skill 會輪流當到狼人和好人。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from engine.factory import ROOT as _R, create_game, load_config, save_replay  # noqa: E402
from engine.roles import BOARDS, ROLES, team_of  # noqa: E402


def _w(s: str) -> int:
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    sp = " " * max(0, width - _w(s))
    return sp + s if right else s + sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--board", default=None, choices=list(BOARDS))
    ap.add_argument("--seed", type=int, default=1, help="起始種子，第 k 局用 seed+k")
    ap.add_argument("--model", default=None, help="把所有玩家改成同一個模型")
    ap.add_argument("--config", default=None)
    ap.add_argument("--save-replays", action="store_true")
    ap.add_argument("--out", default=None, help="把結果存成 JSON")
    args = ap.parse_args()

    cfg = load_config(args.config)
    board = args.board or cfg.get("board", "9")
    n = len(BOARDS[board]["roles"])
    players = cfg["players"][:n]
    if args.model:
        players = [dict(p, model=args.model) for p in players]

    stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # skill -> bucket -> [wins, games]
    fallbacks = defaultdict(int)
    winners = defaultdict(int)
    t0 = time.time()
    for k in range(args.games):
        seed = args.seed + k
        # 每局把座位旋轉一下，避免座位順序影響
        rot = k % n
        ps = players[rot:] + players[:rot]
        game = create_game(ps, cfg["models"], board=board, seed=seed, rules=cfg.get("rules"))
        game.run()
        winners[game.winner] += 1
        for p in game.players:
            team = team_of(p.role)
            win = int(game.winner == team)
            for bucket in ("總計", "狼人陣營" if team == "wolf" else "好人陣營", ROLES[p.role]["name"]):
                stats[p.skill][bucket][0] += win
                stats[p.skill][bucket][1] += 1
            stats[p.skill]["存活到最後"][0] += int(p.alive)
            stats[p.skill]["存活到最後"][1] += 1
        for ev in game.events:
            if ev["type"] == "fallback":
                fallbacks[game.p(ev["data"]["seat"]).skill] += 1
        if args.save_replays:
            save_replay(game, {"players": ps, "board": board, "tournament": True})
        bar = "█" * int(30 * (k + 1) / args.games)
        print(f"\r[{bar:<30}] {k + 1}/{args.games}  狼勝 {winners['wolf']}  好人勝 {winners['village']}", end="", flush=True)
    print(f"\n\n耗時 {time.time() - t0:.1f} 秒，板子：{BOARDS[board]['name']}")
    cols = ["總計", "好人陣營", "狼人陣營", "預言家", "女巫", "獵人", "守衛", "村民", "狼人", "存活到最後"]
    print("\n" + pad("skill", 14) + "".join(pad(c, 12, True) for c in cols))
    rows = sorted(stats.items(), key=lambda kv: -kv[1]["總計"][0] / max(1, kv[1]["總計"][1]))
    result = {}
    for skill, b in rows:
        line = pad(skill[:12], 14)
        result[skill] = {}
        for c in cols:
            w, g = b.get(c, [0, 0])
            result[skill][c] = {"wins": w, "games": g}
            line += pad(f"{100 * w / g:5.1f}%({g:>3})" if g else "-", 12, True)
        print(line)
    if fallbacks:
        print("\nLLM 回應失敗、改用預設策略的次數：", dict(fallbacks))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"board": board, "games": args.games, "winners": winners, "stats": result}, f, ensure_ascii=False, indent=2)
        print(f"結果已存到 {args.out}")


if __name__ == "__main__":
    main()

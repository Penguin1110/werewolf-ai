"""狼人殺遊戲引擎（主持人 / 上帝）。

設計參考：
- Werewolf Arena (Google)：投票與技能選項的順序每次隨機打亂，避免 LLM 的位置偏誤。
- AIWolf：嚴格的資訊隔離，每個 Agent 只會收到自己有權知道的事件。
- 各種開源中文狼人殺：屠邊規則、女巫雙藥互斥、守衛不能連守、同守同救奶穿。
- deepwolf：固定 seed 可重現；不合法的行動由引擎驗證並退回預設策略。

所有事件都會帶有 vis（可見性）欄位：
  "all"          -> 所有人都看得到
  [座位號, ...]   -> 只有這些玩家看得到
  []             -> 只有上帝 / 觀戰者看得到（例如 AI 的內心想法）
"""
from __future__ import annotations

import random
import time
import traceback
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from .roles import BOARDS, ROLES, role_name, team_of
from .narrate import narrate
from .claims import extract_claim, normalize_claim

GOD = []  # 只有觀戰者可見


class Player:
    def __init__(self, seat: int, name: str, role: str, agent, skill: str, model: str):
        self.seat = seat
        self.name = name
        self.role = role
        self.agent = agent
        self.skill = skill
        self.model = model
        self.alive = True

    @property
    def team(self) -> str:
        return team_of(self.role)

    def label(self) -> str:
        return f"{self.seat}號{self.name}"


class GameAborted(Exception):
    pass


class Game:
    def __init__(self, player_specs: List[Dict[str, Any]], board: str = "9", seed: Optional[int] = None,
                 on_event: Optional[Callable[[dict], None]] = None, rules: Optional[dict] = None,
                 fallback_factory: Optional[Callable[[], Any]] = None):
        """player_specs: [{name, agent, skill, model}]，長度需等於板子人數。"""
        roles = list(BOARDS[board]["roles"])
        if len(player_specs) != len(roles):
            raise ValueError(f"{board} 人局需要 {len(roles)} 位玩家，目前有 {len(player_specs)} 位")
        self.seed = seed if seed is not None else random.randrange(1, 10 ** 9)
        self.rng = random.Random(self.seed)
        self.board = board
        self.rng.shuffle(roles)
        self.players: List[Player] = []
        for i, (spec, role) in enumerate(zip(player_specs, roles), start=1):
            self.players.append(Player(i, spec["name"], role, spec["agent"], spec.get("skill", "?"), spec.get("model", "?")))
        self.rules = {"majority_win": False, "max_days": 15, "first_night_last_words": True,
                      "speech_max_chars": 400, "think_max_chars": 600}
        self.rules.update(rules or {})
        self.events: List[dict] = []
        self.on_event = on_event
        self.fallback_factory = fallback_factory
        self.day = 0
        self.phase = "setup"
        self.winner: Optional[str] = None
        self.aborted = False
        # 私有狀態
        self.seer_results: Dict[int, str] = {}
        self.witch_antidote = True
        self.witch_poison = True
        self.guard_last: Optional[int] = None
        self._fallbacks: Dict[int, Any] = {}

    # ------------------------------------------------------------------ 基礎工具
    def p(self, seat: int) -> Player:
        return self.players[seat - 1]

    def alive(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def alive_seats(self) -> List[int]:
        return [p.seat for p in self.players if p.alive]

    def wolves(self, alive_only: bool = True) -> List[Player]:
        return [p for p in self.players if p.role == "werewolf" and (p.alive or not alive_only)]

    def by_role(self, role: str) -> Optional[Player]:
        for p in self.players:
            if p.role == role:
                return p
        return None

    def emit(self, type_: str, data: dict, vis: Any = "all") -> dict:
        if self.aborted:
            raise GameAborted()
        ev = {"i": len(self.events), "t": round(time.time(), 3), "type": type_, "day": self.day,
              "phase": self.phase, "vis": vis, "data": data}
        ev["text"] = narrate(ev, self)
        self.events.append(ev)
        if self.on_event:
            try:
                self.on_event(ev)
            except Exception:
                traceback.print_exc()
        return ev

    def visible_events(self, seat: int) -> List[dict]:
        out = []
        for ev in self.events:
            v = ev["vis"]
            if v == "all" or (isinstance(v, list) and seat in v):
                out.append(ev)
        return out

    def view_for(self, player: Player) -> dict:
        """提供給 Agent 的「玩家視角」，只包含他有權知道的資訊。"""
        view = {
            "seat": player.seat, "name": player.name, "role": player.role, "role_name": role_name(player.role),
            "team": player.team, "day": self.day, "phase": self.phase, "board": self.board,
            "players": [{"seat": p.seat, "name": p.name, "alive": p.alive} for p in self.players],
            "alive": self.alive_seats(),
            "dead": [p.seat for p in self.players if not p.alive],
            "board_roles": {r: BOARDS[self.board]["roles"].count(r) for r in set(BOARDS[self.board]["roles"])},
            "history": [{k: ev[k] for k in ("i", "type", "day", "phase", "data", "text")}
                        for ev in self.visible_events(player.seat)],
            "private": {},
            "rules": dict(self.rules),
        }
        if player.role == "werewolf":
            view["teammates"] = [w.seat for w in self.wolves(alive_only=False) if w.seat != player.seat]
        if player.role == "seer":
            view["private"]["seer_results"] = dict(self.seer_results)
        if player.role == "witch":
            view["private"]["antidote"] = self.witch_antidote
            view["private"]["poison"] = self.witch_poison
        if player.role == "guard":
            view["private"]["guard_last"] = self.guard_last
        return view

    # ------------------------------------------------------------------ 呼叫 Agent
    def _fallback(self, player: Player):
        if player.seat not in self._fallbacks and self.fallback_factory:
            self._fallbacks[player.seat] = self.fallback_factory()
        return self._fallbacks.get(player.seat)

    def ask(self, player: Player, kind: str, options: Optional[List[int]] = None, allow_none: bool = False,
            info: Optional[dict] = None) -> dict:
        options = list(options or [])
        shuffled = options[:]
        self.rng.shuffle(shuffled)  # 打亂選項順序，降低 LLM 位置偏誤
        req = {"kind": kind, "options": shuffled, "allow_none": allow_none, "info": info or {}}
        self.emit("acting", {"seat": player.seat, "kind": kind}, vis=GOD)
        view = self.view_for(player)
        resp, source, err = None, "agent", None
        try:
            resp = player.agent.act(req, view)
            err = self._validate(req, resp)
        except GameAborted:
            raise
        except Exception as e:  # LLM 掛掉、JSON 壞掉等
            err = f"{type(e).__name__}: {e}"
        if err:
            fb = self._fallback(player)
            self.emit("fallback", {"seat": player.seat, "kind": kind, "error": str(err)[:300]}, vis=GOD)
            source = "fallback"
            resp = fb.act(req, view) if fb else {}
            if self._validate(req, resp):
                resp = self._default_response(req)
        resp = dict(resp or {})
        thinking = str(resp.get("thinking") or "").strip()
        if thinking:
            self.emit("thought", {"seat": player.seat, "kind": kind, "text": thinking[: self.rules["think_max_chars"]],
                                  "source": source}, vis=GOD)
        if "speech" in resp and resp["speech"] is not None:
            resp["speech"] = str(resp["speech"]).strip()[: self.rules["speech_max_chars"]] or "（沉默）"
        return resp

    def _validate(self, req: dict, resp: Any) -> Optional[str]:
        if not isinstance(resp, dict):
            return "回傳必須是 dict"
        kind = req["kind"]
        if kind in ("speech", "last_words", "wolf_chat", "pk_speech"):
            if not isinstance(resp.get("speech"), str):
                return "缺少 speech 字串"
            return None
        if kind == "witch":
            save = bool(resp.get("save"))
            poison = resp.get("poison")
            if save and not req["info"].get("can_save"):
                return "不能使用解藥"
            if poison is not None:
                try:
                    poison = int(poison)
                except (TypeError, ValueError):
                    return "poison 必須是座位號或 null"
                if not req["info"].get("can_poison") or poison not in req["options"]:
                    return "不能毒這個人"
                if save:
                    return "同一晚不能同時用兩瓶藥"
            return None
        target = resp.get("target")
        if target is None:
            return None if req["allow_none"] else "必須選擇一個目標"
        try:
            target = int(target)
        except (TypeError, ValueError):
            return "target 必須是整數座位號"
        if target not in req["options"]:
            return f"{target} 不在可選目標 {sorted(req['options'])} 中"
        resp["target"] = target
        return None

    def _default_response(self, req: dict) -> dict:
        if req["kind"] in ("speech", "last_words", "wolf_chat", "pk_speech"):
            return {"speech": "過。"}
        if req["kind"] == "witch":
            return {"save": False, "poison": None}
        if req["allow_none"] or not req["options"]:
            return {"target": None}
        return {"target": self.rng.choice(req["options"])}

    # ------------------------------------------------------------------ 勝負
    def check_win(self) -> Optional[str]:
        wolves = len(self.wolves())
        goods = [p for p in self.alive() if p.team == "village"]
        gods = [p for p in goods if ROLES[p.role]["god"]]
        villagers = [p for p in goods if p.role == "villager"]
        if wolves == 0:
            return "village"
        if not gods or not villagers:  # 屠邊
            return "wolf"
        if self.rules["majority_win"] and wolves >= len(goods):
            return "wolf"
        return None

    def _finish(self, winner: Optional[str], reason: str):
        self.winner = winner
        self.phase = "end"
        self.emit("game_over", {"winner": winner, "reason": reason,
                                "roles": {p.seat: p.role for p in self.players}})

    # ------------------------------------------------------------------ 主流程
    def run(self) -> Optional[str]:
        try:
            self._run()
        except GameAborted:
            self.aborted = False
            self._finish(None, "遊戲被中止")
        return self.winner

    def abort(self):
        self.aborted = True

    def _run(self):
        self.emit("game_start", {
            "board": self.board, "board_name": BOARDS[self.board]["name"], "seed": self.seed,
            "players": [{"seat": p.seat, "name": p.name, "skill": p.skill, "model": p.model} for p in self.players],
            "board_roles": BOARDS[self.board]["roles"],
        })
        self.emit("role_assign", {"roles": {p.seat: p.role for p in self.players}}, vis=GOD)
        for p in self.players:
            data = {"seat": p.seat, "role": p.role}
            if p.role == "werewolf":
                data["teammates"] = [w.seat for w in self.wolves() if w.seat != p.seat]
            self.emit("your_role", data, vis=[p.seat])
        for p in self.players:
            try:
                if hasattr(p.agent, "on_game_start"):
                    p.agent.on_game_start(self.view_for(p))
            except Exception:
                traceback.print_exc()

        while True:
            self.day += 1
            if self.day > self.rules["max_days"]:
                return self._finish(None, "超過天數上限，平局")
            self.night()
            w = self.check_win()
            if w:
                return self._finish(w, self._reason(w))
            self.daytime()
            w = self.check_win()
            if w:
                return self._finish(w, self._reason(w))

    def _reason(self, w: str) -> str:
        if w == "village":
            return "所有狼人都已出局"
        goods = [p for p in self.alive() if p.team == "village"]
        if not [p for p in goods if ROLES[p.role]["god"]]:
            return "神職全滅（屠邊）"
        if not [p for p in goods if p.role == "villager"]:
            return "村民全滅（屠邊）"
        return "狼人數量已不少於好人"

    # ------------------------------------------------------------------ 夜晚
    def night(self):
        self.phase = "night"
        self.emit("phase", {"phase": "night", "day": self.day})
        alive_seats = self.alive_seats()

        # 守衛
        protected = None
        guard = self.by_role("guard")
        if guard and guard.alive:
            opts = [s for s in alive_seats if s != self.guard_last]
            r = self.ask(guard, "guard", opts, allow_none=True)
            protected = r.get("target")
            self.guard_last = protected
            self.emit("guard", {"seat": guard.seat, "target": protected}, vis=[guard.seat])

        # 狼人
        wolves = self.wolves()
        wolf_seats = [w.seat for w in self.wolves(alive_only=False)]
        victim = None
        if wolves:
            for w in wolves:
                r = self.ask(w, "wolf_chat")
                self.emit("wolf_chat", {"seat": w.seat, "text": r["speech"]}, vis=wolf_seats)
            targets = [s for s in alive_seats if self.p(s).role != "werewolf"]
            votes = {}
            for w in wolves:
                r = self.ask(w, "wolf_kill", targets, allow_none=False)
                votes[w.seat] = r.get("target")
                self.emit("wolf_vote", {"seat": w.seat, "target": r.get("target")}, vis=wolf_seats)
            tally = Counter(v for v in votes.values() if v is not None)
            if tally:
                top = max(tally.values())
                cands = sorted(s for s, c in tally.items() if c == top)
                victim = cands[0] if len(cands) == 1 else self.rng.choice(cands)
            self.emit("wolf_kill", {"target": victim}, vis=wolf_seats)

        # 預言家
        seer = self.by_role("seer")
        if seer and seer.alive:
            opts = [s for s in alive_seats if s != seer.seat]
            r = self.ask(seer, "seer_check", opts, allow_none=False)
            t = r.get("target")
            if t is not None:
                result = "wolf" if self.p(t).role == "werewolf" else "good"
                self.seer_results[t] = result
                self.emit("seer_check", {"seat": seer.seat, "target": t, "result": result}, vis=[seer.seat])

        # 女巫
        saved = False
        poisoned = None
        witch = self.by_role("witch")
        if witch and witch.alive and (self.witch_antidote or self.witch_poison):
            known_victim = victim if self.witch_antidote else None
            info = {"victim": known_victim,
                    "can_save": bool(self.witch_antidote and victim is not None and victim != witch.seat),
                    "can_poison": self.witch_poison}
            self.emit("witch_info", {"seat": witch.seat, "victim": known_victim}, vis=[witch.seat])
            opts = [s for s in alive_seats if s != witch.seat]
            r = self.ask(witch, "witch", opts, allow_none=True, info=info)
            if r.get("save") and info["can_save"]:
                saved = True
                self.witch_antidote = False
            elif r.get("poison") is not None and self.witch_poison:
                poisoned = int(r["poison"])
                self.witch_poison = False
            self.emit("witch", {"seat": witch.seat, "save": victim if saved else None, "poison": poisoned},
                      vis=[witch.seat])

        # 結算
        deaths = []
        if victim is not None:
            guarded = protected == victim
            if guarded and saved:
                deaths.append((victim, "wolf"))  # 同守同救 = 奶穿
            elif not guarded and not saved:
                deaths.append((victim, "wolf"))
        if poisoned is not None and poisoned not in [d[0] for d in deaths]:
            deaths.append((poisoned, "poison"))
        self._night_deaths = deaths

    # ------------------------------------------------------------------ 白天
    def daytime(self):
        self.phase = "day"
        self.emit("phase", {"phase": "day", "day": self.day})
        deaths = sorted(self._night_deaths)
        self.emit("night_result", {"deaths": [d[0] for d in deaths]})
        for seat, cause in deaths:
            self.kill(seat, cause, public_cause="night")
        if self.check_win():
            return
        if self.day == 1 and self.rules["first_night_last_words"]:
            for seat, cause in deaths:
                self.last_words(seat)
        for seat, cause in deaths:
            if self.p(seat).role == "hunter" and cause != "poison":
                self.hunter(seat)
                if self.check_win():
                    return

        # 發言順序：從第一個死者的下一位開始，否則隨機
        alive = self.alive_seats()
        n = len(self.players)
        start = (deaths[0][0] % n) + 1 if deaths else self.rng.choice(alive)
        order = [((start - 1 + k) % n) + 1 for k in range(n)]
        order = [s for s in order if self.p(s).alive]
        if self.rng.random() < 0.5:
            order = [order[0]] + list(reversed(order[1:]))
        self.emit("speech_order", {"order": order})
        for s in order:
            r = self.ask(self.p(s), "speech")
            self.emit("speech", {"seat": s, "text": r["speech"], "claim": self._claim(r)})

        # 投票
        exiled = self.vote_round(self.alive_seats(), self.alive_seats(), "vote")
        if exiled == "tie":
            cands = self._last_tie
            self.emit("pk_start", {"candidates": cands})
            for s in cands:
                r = self.ask(self.p(s), "pk_speech", info={"candidates": cands})
                self.emit("speech", {"seat": s, "text": r["speech"], "pk": True, "claim": self._claim(r)})
            voters = [s for s in self.alive_seats() if s not in cands]
            exiled = self.vote_round(voters, cands, "pk_vote")
            if exiled == "tie":
                self.emit("no_exile", {"reason": "PK 後仍然平票，今天無人出局"})
                exiled = None
        if exiled:
            self.kill(exiled, "exile", public_cause="exile")
            if self.check_win():
                return
            self.last_words(exiled)
            if self.p(exiled).role == "hunter":
                self.hunter(exiled)

    def _claim(self, r: dict):
        return normalize_claim(r.get("claim")) or extract_claim(r.get("speech", ""))

    def vote_round(self, voters: List[int], candidates: List[int], kind: str):
        votes = {}
        for s in voters:
            opts = [c for c in candidates if c != s]
            r = self.ask(self.p(s), kind, opts, allow_none=True, info={"candidates": candidates})
            votes[s] = r.get("target")
        for s in voters:
            self.emit("vote", {"seat": s, "target": votes[s], "pk": kind == "pk_vote"})
        tally = Counter(v for v in votes.values() if v is not None)
        if not tally:
            self.emit("vote_result", {"tally": {}, "exiled": None, "tie": []})
            return None
        top = max(tally.values())
        tops = sorted(s for s, c in tally.items() if c == top)
        if len(tops) > 1:
            self._last_tie = tops
            self.emit("vote_result", {"tally": dict(tally), "exiled": None, "tie": tops})
            return "tie"
        self.emit("vote_result", {"tally": dict(tally), "exiled": tops[0], "tie": []})
        return tops[0]

    def kill(self, seat: int, cause: str, public_cause: str):
        p = self.p(seat)
        if not p.alive:
            return
        p.alive = False
        self.emit("death", {"seat": seat, "public_cause": public_cause})
        self.emit("death_detail", {"seat": seat, "cause": cause, "role": p.role}, vis=GOD)

    def last_words(self, seat: int):
        r = self.ask(self.p(seat), "last_words")
        self.emit("last_words", {"seat": seat, "text": r["speech"], "claim": self._claim(r)})

    def hunter(self, seat: int):
        opts = self.alive_seats()
        r = self.ask(self.p(seat), "hunter_shoot", opts, allow_none=True)
        t = r.get("target")
        self.emit("hunter_shoot", {"seat": seat, "target": t})
        if t is not None:
            self.kill(t, "shot", public_cause="shot")
            if not self.check_win():
                self.last_words(t)

    # ------------------------------------------------------------------ 匯出
    def replay(self, meta: Optional[dict] = None) -> dict:
        return {"format": "werewolf-ai-replay/1", "seed": self.seed, "board": self.board, "winner": self.winner,
                "meta": meta or {}, "events": self.events}

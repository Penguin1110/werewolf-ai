"""AI 玩家。

每個 Agent 只需要實作一個方法：

    act(request: dict, view: dict) -> dict

request = {"kind": 動作種類, "options": [可選座位], "allow_none": 可否不選, "info": {...}}
view    = 該玩家視角的遊戲狀態（見 Game.view_for），包含他看得到的所有歷史事件。

回傳欄位依動作而定：
  發言類 (speech / wolf_chat / last_words / pk_speech) -> {"speech": "...", "claim": {...}?}
  選人類 (vote / pk_vote / wolf_kill / seer_check / guard / hunter_shoot) -> {"target": 座位 or None}
  女巫 (witch) -> {"save": bool, "poison": 座位 or None}
  任何動作都可以加 "thinking"（內心獨白，只有觀戰者看得到）與 "notes"（自己的筆記，下回合會再看到）。
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from . import llm
from .roles import BOARDS, ROLES, role_name

SPEECH_KINDS = ("speech", "wolf_chat", "last_words", "pk_speech")


# ============================================================================ 共用分析
def analyze(view: dict) -> dict:
    """從玩家可見的歷史中整理出：誰跳了什麼身分、誰報了誰的查驗、投票紀錄。"""
    claims: Dict[int, dict] = {}
    claim_order: List[int] = []
    votes: List[tuple] = []  # (day, voter, target)
    dead_roles: Dict[int, str] = {}
    night_victims: List[int] = []
    for ev in view["history"]:
        t, d = ev["type"], ev["data"]
        if t in ("speech", "last_words") and d.get("claim"):
            c = d["claim"]
            s = d["seat"]
            if s not in claims:
                claims[s] = {"role": c.get("role"), "checks": {}}
                claim_order.append(s)
            if c.get("role"):
                claims[s]["role"] = c["role"]
            for k, v in (c.get("checks") or {}).items():
                claims[s]["checks"][int(k)] = v
        elif t == "vote" and not d.get("pk"):
            votes.append((ev["day"], d["seat"], d["target"]))
        elif t == "night_result":
            night_victims.extend(d["deaths"])
    seer_claimers = [s for s in claim_order if claims[s]["role"] == "seer"]
    return {"claims": claims, "seer_claimers": seer_claimers, "votes": votes, "night_victims": night_victims}


def suspicion(view: dict, a: dict, rng: random.Random) -> Dict[int, float]:
    """好人視角的懷疑度：越高越像狼。"""
    me = view["seat"]
    alive = set(view["alive"])
    score = {s: rng.random() * 0.8 for s in alive if s != me}
    my_checks = view["private"].get("seer_results", {}) if view["role"] == "seer" else {}
    seers = [s for s in a["seer_claimers"] if s != me]
    # 推定誰是真預言家：夜裡被刀死的、或被女巫救過的跳預言家者，幾乎一定是真的
    trusted = None
    for c in seers:
        if c in a["night_victims"]:
            trusted = c
    if view["role"] == "witch":
        for ev in view["history"]:
            if ev["type"] == "witch" and ev["data"].get("save") in seers:
                trusted = ev["data"]["save"]
    for idx, c in enumerate(seers):
        weight = 1.0
        if view["role"] == "seer":
            weight = -1.0  # 我才是真預言家，其他跳預言家的都是狼
            if c in score:
                score[c] += 12
        elif trusted is not None and len(seers) > 1:
            weight = 1.5 if c == trusted else -0.5
            if c != trusted and c in score:
                score[c] += 6
        elif len(seers) > 1:
            weight = 0.6
            if c in score:
                score[c] += 1.0
                # 後跳、而且一跳就查殺先跳者的人，比較像悍跳狼
                if idx > 0 and a["claims"][c]["checks"].get(seers[0]) == "wolf":
                    score[c] += 1.6
                    weight = 0.3
        for t, res in a["claims"][c]["checks"].items():
            if t not in score:
                continue
            if res == "wolf":
                score[t] += 3.0 * weight
            else:
                score[t] -= 1.5 * weight
    # 對被預言家給金水（好人）的人投票的人，有點可疑
    golds = {t for c in seers for t, r in a["claims"][c]["checks"].items() if r == "good"}
    for day, voter, target in a["votes"]:
        if voter in score and target in golds:
            score[voter] += 0.6
    # 公開發言中被大家點名的人（形成共識，減少分票）
    for ev in view["history"]:
        if ev["type"] == "speech" and ev["day"] == view["day"]:
            for m in re.finditer(r"(?:覺得|關注|出|投)\s*(\d{1,2})\s*號", ev["data"]["text"]):
                t = int(m.group(1))
                if t in score and t != ev["data"]["seat"]:
                    score[t] += 0.35
    # 第一夜被刀的人一定是好人；救過的人也大概是好人
    for s in a["night_victims"]:
        score.pop(s, None)
    if view["role"] == "witch":
        for ev in view["history"]:
            if ev["type"] == "witch" and ev["data"].get("save") and ev["data"]["save"] in score:
                score[ev["data"]["save"]] -= 2.5
    for t, res in my_checks.items():
        t = int(t)
        if t in score:
            score[t] += 100 if res == "wolf" else -100
    # 跳獵人、女巫等神職（無人對跳）稍微降低懷疑
    for s, c in a["claims"].items():
        if s in score and c.get("role") in ("hunter", "witch", "guard"):
            rivals = [x for x, cc in a["claims"].items() if cc.get("role") == c["role"] and x != s]
            score[s] += 1.5 if rivals else -1.0
    return score


def top(score: Dict[int, float], options: List[int]) -> Optional[int]:
    cands = [s for s in options if s in score]
    if not cands:
        return None
    return max(cands, key=lambda s: score[s])


# ============================================================================ 規則 AI
class RuleAgent:
    """不需要任何 LLM 的規則型 AI，可當離線對手，也當 LLM 出錯時的備援。

    style 參數（可在 SKILL.md frontmatter 用 rule_* 設定）：
      fake_claim  狼人悍跳預言家的機率（0~1）
      chatty      發言是否多講幾句
    """

    def __init__(self, seed: Optional[int] = None, style: Optional[dict] = None, skill=None):
        self.rng = random.Random(seed)
        self.style = {"fake_claim": 0.35, "chatty": True}
        self.style.update(style or {})
        self.skill = skill
        self.memory: Dict[str, Any] = {}

    def act(self, req: dict, view: dict) -> dict:
        if self.skill and self.skill.hook("decide"):
            r = self.skill.hook("decide")(req, view, self.memory)
            if r:
                return r
        kind = req["kind"]
        fn = getattr(self, "_" + kind)
        return fn(req, view, analyze(view))

    # ---------------- 小工具
    def _wolves(self, view):
        return set(view.get("teammates", [])) | ({view["seat"]} if view["role"] == "werewolf" else set())

    def _public_heat(self, view, a) -> Dict[int, float]:
        """所有人公開看得到的懷疑度（狼人用來帶風向）。"""
        heat = {s: self.rng.random() * 0.5 for s in view["alive"]}
        for c in a["seer_claimers"]:
            for t, r in a["claims"][c]["checks"].items():
                if t in heat:
                    heat[t] += 3 if r == "wolf" else -1.5
        for day, voter, target in a["votes"]:
            if target in heat and day == view["day"] - 1:
                heat[target] += 0.4
        return heat

    def _fake_seer(self, view, a) -> Optional[dict]:
        """狼人悍跳：只讓一隻狼跳，避免狼隊撞車。"""
        wolves = self._wolves(view)
        if any(c in wolves for c in a["seer_claimers"]):
            mine = a["claims"].get(view["seat"])
            if mine and mine.get("role") == "seer":
                return mine
            return None
        if view["day"] != 1 or self.memory.get("decided_fake") is not None:
            return None
        alive_wolves = sorted(w for w in wolves if w in view["alive"])
        if not alive_wolves or alive_wolves[0] != view["seat"]:
            self.memory["decided_fake"] = False
            return None
        self.memory["decided_fake"] = self.rng.random() < float(self.style["fake_claim"])
        return {} if self.memory["decided_fake"] else None

    # ---------------- 夜晚
    def _wolf_chat(self, req, view, a):
        target = self._wolf_target(view, a)
        mates = "、".join(f"{s}號" for s in view.get("teammates", []) if s in view["alive"]) or "（隊友都倒了）"
        lines = [f"隊友 {mates}，我建議今晚刀 {target}號。"]
        wolves = self._wolves(view)
        real = [c for c in a["seer_claimers"] if c not in wolves and c in view["alive"]]
        fake = [c for c in a["seer_claimers"] if c in wolves]
        if real:
            lines.append(f"{real[0]}號是真預言家，優先處理他。")
        if fake:
            lines.append(f"白天繼續站邊 {fake[0]}號的悍跳。")
        elif view["day"] == 1 and not a["seer_claimers"]:
            lines.append("白天大家先低調，不要互保太明顯。")
        return {"speech": "".join(lines), "thinking": f"刀口優先順序：預言家 > 疑似神職 > 金水。選 {target}號。"}

    def _wolf_target(self, view, a):
        wolves = self._wolves(view)
        opts = [s for s in view["alive"] if s not in wolves]
        if not opts:
            return None
        real_seers = [s for s in a["seer_claimers"] if s not in wolves and s in opts]
        if real_seers:
            return real_seers[0]
        gods = [s for s, c in a["claims"].items() if s in opts and c.get("role") in ("witch", "guard")]
        if gods:
            return gods[0]
        golds = [t for c in a["seer_claimers"] for t, r in a["claims"][c]["checks"].items() if r == "good" and t in opts]
        hunters = {s for s, c in a["claims"].items() if c.get("role") == "hunter"}
        safe = [s for s in (golds or opts) if s not in hunters] or opts
        return self.rng.choice(safe)

    def _wolf_kill(self, req, view, a):
        # 先看狼隊友在頻道裡說要刀誰，跟票
        for ev in reversed(view["history"]):
            if ev["type"] == "wolf_chat" and ev["day"] == view["day"]:
                m = re.search(r"刀\s*(\d+)\s*號", ev["data"]["text"])
                if m and int(m.group(1)) in req["options"]:
                    return {"target": int(m.group(1)), "thinking": "跟隨隊友的刀口，集中票數。"}
        t = self._wolf_target(view, a)
        return {"target": t if t in req["options"] else self.rng.choice(req["options"])}

    def _seer_check(self, req, view, a):
        checked = {int(k) for k in view["private"].get("seer_results", {})}
        sc = suspicion(view, a, self.rng)
        opts = [s for s in req["options"] if s not in checked] or req["options"]
        t = top(sc, opts) if view["day"] > 1 else self.rng.choice(opts)
        return {"target": t, "thinking": f"查驗還沒驗過、目前最可疑的 {t}號。"}

    def _witch(self, req, view, a):
        info = req["info"]
        victim = info.get("victim")
        if info.get("can_save") and victim is not None:
            if view["day"] == 1 or victim in a["seer_claimers"]:
                return {"save": True, "poison": None, "thinking": f"{victim}號被刀，價值高，用解藥救。"}
        if info.get("can_poison") and view["day"] >= 2:
            sc = suspicion(view, a, self.rng)
            t = top(sc, req["options"])
            if t is not None and sc[t] >= 2.5:
                return {"save": False, "poison": t, "thinking": f"{t}號被查殺或極度可疑，毒掉他。"}
        return {"save": False, "poison": None, "thinking": "今晚先不用藥，保留資源。"}

    def _guard(self, req, view, a):
        seers = [s for s in a["seer_claimers"] if s in req["options"]]
        if seers:
            return {"target": seers[0], "thinking": f"守跳出來的預言家 {seers[0]}號。"}
        if view["day"] == 1:
            return {"target": None, "thinking": "首夜空守，避免和女巫同守同救。"}
        return {"target": self.rng.choice(req["options"]) if req["options"] else None}

    def _hunter_shoot(self, req, view, a):
        sc = suspicion(view, a, self.rng)
        t = top(sc, req["options"])
        if t is None or sc.get(t, 0) < 2.5:
            return {"target": None, "thinking": "沒有足夠把握，不開槍以免誤傷好人。"}
        return {"target": t, "thinking": f"{t}號最像狼，帶走他。"}

    # ---------------- 投票
    def _vote(self, req, view, a):
        if view["role"] == "werewolf":
            wolves = self._wolves(view)
            heat = self._public_heat(view, a)
            opts = [s for s in req["options"] if s not in wolves] or req["options"]
            # 如果有真預言家（不是狼跳的），優先投他
            real = [s for s in a["seer_claimers"] if s not in wolves and s in opts]
            if real and any(w in a["seer_claimers"] for w in wolves):
                return {"target": real[0], "thinking": "和真預言家對跳中，把他投出去。"}
            t = top(heat, opts)
            return {"target": t, "thinking": f"跟著場上風向投 {t}號，混在好人裡。"}
        sc = suspicion(view, a, self.rng)
        t = top(sc, req["options"])
        return {"target": t, "thinking": f"綜合查驗與發言，{t}號最可疑。"}

    _pk_vote = _vote

    # ---------------- 發言
    def _speech(self, req, view, a):
        role = view["role"]
        me = view["seat"]
        if role == "seer":
            checks = {int(k): v for k, v in view["private"].get("seer_results", {}).items()}
            txt = ["我是預言家。"]
            for t, r in checks.items():
                txt.append(f"{t}號是{'查殺，他是狼' if r == 'wolf' else '金水，是好人'}。")
            others = [s for s in a["seer_claimers"] if s != me]
            if others:
                txt.append(f"{'、'.join(str(s) for s in others)}號跟我對跳，必定是狼，請好人站邊我。")
            wolves = [t for t, r in checks.items() if r == "wolf" and t in view["alive"]]
            if wolves:
                txt.append(f"今天全票出 {wolves[0]}號。")
            claim = {"role": "seer", "checks": {str(t): r for t, r in checks.items()}}
            return {"speech": "".join(txt), "claim": claim, "thinking": "公開身分與查驗，帶領好人。"}
        if role == "werewolf":
            fake = self._fake_seer(view, a)
            if fake is not None:
                wolves = self._wolves(view)
                prev = a["claims"].get(me, {}).get("checks", {})
                checks = {int(k): v for k, v in prev.items()}
                goods = [s for s in view["alive"] if s not in wolves and s not in checks]
                real = [s for s in a["seer_claimers"] if s != me]
                if real and real[0] not in checks:
                    checks[real[0]] = "wolf"
                elif goods:
                    checks[self.rng.choice(goods)] = "wolf"
                txt = ["我才是真預言家。" if real else "我是預言家。"]
                for t, r in checks.items():
                    txt.append(f"{t}號{'查殺' if r == 'wolf' else '金水'}。")
                if real:
                    txt.append(f"{real[0]}號是悍跳的狼，大家不要被騙。")
                tgt = [t for t, r in checks.items() if r == "wolf" and t in view["alive"]]
                if tgt:
                    txt.append(f"今天請出 {tgt[0]}號。")
                claim = {"role": "seer", "checks": {str(t): r for t, r in checks.items()}}
                return {"speech": "".join(txt), "claim": claim, "thinking": "悍跳預言家，發假查殺搶警徽流話語權。"}
            heat = self._public_heat(view, a)
            wolves = self._wolves(view)
            opts = [s for s in view["alive"] if s not in wolves and s != me]
            t = top(heat, opts)
            return {"speech": self._villager_line(view, a, t, fake=True),
                    "thinking": f"裝好人，把焦點引到 {t}號身上。"}
        # 好人
        sc = suspicion(view, a, self.rng)
        t = top(sc, [s for s in view["alive"] if s != me])
        resp = {"speech": self._villager_line(view, a, t), "thinking": f"目前懷疑 {t}號。"}
        if role == "hunter" and sc and self._am_hot(view, a):
            resp["speech"] = "我是獵人，今天投我出去我會開槍帶人。" + resp["speech"]
            resp["claim"] = {"role": "hunter", "checks": {}}
        return resp

    def _am_hot(self, view, a):
        me = view["seat"]
        for c in a["seer_claimers"]:
            if a["claims"][c]["checks"].get(me) == "wolf":
                return True
        return False

    def _villager_line(self, view, a, t, fake=False):
        seers = a["seer_claimers"]
        parts = [self.rng.choice(["我是好人，", "我這邊是一張好人牌，", "我身分不重要，是好人，"])]
        if len(seers) >= 2:
            pick = seers[0] if not fake else seers[-1]
            parts.append(f"現在 {seers[0]}號和 {seers[1]}號對跳預言家，我比較相信 {pick}號。")
        elif len(seers) == 1:
            s = seers[0]
            ch = a["claims"][s]["checks"]
            wolves = [x for x, r in ch.items() if r == "wolf"]
            parts.append(f"{s}號跳預言家，" + (f"他給 {wolves[0]}號查殺，我暫時跟。" if wolves else "目前沒有對跳，先認他。"))
        else:
            parts.append("目前還沒有人跳預言家，資訊很少。")
        if t:
            reason = self.rng.choice(["發言太空泛", "一直在划水", "站邊很奇怪", "投票跟風", "邏輯前後矛盾"])
            parts.append(f"我覺得 {t}號{reason}，今天我關注他。")
        if self.style.get("chatty"):
            parts.append(self.rng.choice(["好人不要分票。", "大家聽發言找狼。", "過。"]))
        return "".join(parts)

    def _last_words(self, req, view, a):
        r = self._speech(req, view, a)
        r["speech"] = "我的遺言：" + r["speech"]
        return r

    def _pk_speech(self, req, view, a):
        r = self._speech(req, view, a)
        r["speech"] = "我在 PK 台上，請大家聽我說。" + r["speech"]
        return r


# ============================================================================ LLM AI
RULES_TEXT = """你正在玩一場「狼人殺」桌遊（中文標準規則），對手都是其他 AI。
陣營：狼人陣營 vs 好人陣營（神職 + 村民）。
- 狼人：每晚和隊友一起刀一人。白天要隱藏身分，可以假跳神職（悍跳預言家）、帶風向。
- 預言家：每晚查驗一人是好人還是狼人。
- 女巫：一瓶解藥、一瓶毒藥，同一晚只能用一瓶，不能自救。
- 獵人：被刀或被投出時可開槍帶走一人；被毒不能開槍。
- 守衛：每晚守護一人，不能連守同一人；同守同救會死（奶穿）。
- 村民：沒有技能。
勝負（屠邊）：狼人全部出局 → 好人勝；所有神職 或 所有村民 出局 → 狼人勝。
流程：夜晚（守衛→狼人→預言家→女巫）→ 白天公布死訊 → 依序發言 → 投票放逐（平票 PK 一次）。
術語：金水=被預言家驗為好人；查殺=被預言家驗為狼；悍跳=狼人假跳預言家；對跳=兩人搶同一身分；站邊=選擇相信誰。
死亡的玩家身分不會公開。"""

KIND_TASK = {
    "speech": "現在輪到你白天公開發言。所有人都會聽到。說出你的分析、你懷疑誰、你要投誰。可以選擇是否公開（或假裝）身分。",
    "pk_speech": "你和其他人平票，進入 PK。這是你最後拉票的機會，說服大家不要投你。",
    "last_words": "你已經出局，請留下遺言（所有人都聽得到）。可以公開身分、報查驗、指認狼人。",
    "wolf_chat": "現在是夜晚的狼人私密頻道，只有狼隊友聽得到。和隊友商量今晚刀誰、白天誰要悍跳或怎麼配合。",
    "wolf_kill": "請選擇今晚要刀殺的玩家（狼隊以多數決，平票隨機）。",
    "seer_check": "請選擇今晚要查驗的玩家。",
    "guard": "請選擇今晚要守護的玩家，也可以空守（target 填 null）。",
    "witch": "女巫請決定今晚的用藥。",
    "vote": "請投票放逐一名玩家，也可以棄票（target 填 null）。",
    "pk_vote": "PK 投票：在台上的候選人中投一個，或棄票。",
    "hunter_shoot": "你是獵人並且出局了，可以開槍帶走一名玩家，也可以不開槍（target 填 null）。",
}


def _seat_list(view, seats):
    names = {p["seat"]: p["name"] for p in view["players"]}
    return "、".join(f"{s}號({names.get(s, '')})" for s in seats) or "（無）"


class LLMAgent:
    def __init__(self, model_cfg: dict, skill=None, seed: Optional[int] = None, history_chars: int = 9000):
        self.cfg = model_cfg
        self.skill = skill
        self.memory: Dict[str, Any] = {"notes": ""}
        self.history_chars = history_chars
        self.rng = random.Random(seed)
        self.last_prompt = None

    def on_game_start(self, view):
        if self.skill and self.skill.hook("on_game_start"):
            self.skill.hook("on_game_start")(view, self.memory)

    # ---------------- prompt
    def system_prompt(self, view: dict) -> str:
        role = view["role"]
        s = [RULES_TEXT, ""]
        counts = "、".join(f"{role_name(r)}×{n}" for r, n in view["board_roles"].items())
        if view.get("rules", {}).get("majority_win"):
            s.append("本局加註：只要存活狼人數 ≥ 存活好人數，狼人立即獲勝。")
        s.append(f"本局板子：{BOARDS[view['board']]['name']}（{counts}）。")
        s.append(f"你是 {view['seat']}號玩家「{view['name']}」，你的真實身分是【{role_name(role)}】：{ROLES[role]['desc']}")
        if role == "werewolf":
            s.append(f"你的狼隊友：{_seat_list(view, view.get('teammates', []))}。絕對不要在白天暴露自己或隊友。")
        if self.skill:
            persona = self.skill.meta.get("persona")
            if persona:
                s.append(f"\n【你的說話風格】{persona}")
            sp = self.skill.prompt_for(role)
            if sp:
                s.append("\n【你的策略手冊（由你的主人撰寫，請優先遵守）】\n" + sp)
        s.append("\n請永遠只輸出一個 JSON 物件，不要有其他文字。發言請用繁體中文、口語、像真人玩家，避免太長（80~200 字）。")
        return "\n".join(s)

    def user_prompt(self, req: dict, view: dict) -> str:
        lines = []
        hist = [ev["text"] for ev in view["history"] if ev["type"] not in ("acting",)]
        text = "\n".join(hist)
        if len(text) > self.history_chars:
            text = "…（較早的紀錄省略）…\n" + text[-self.history_chars:]
        lines.append("【你看得到的遊戲紀錄】\n" + text)
        lines.append(f"\n【目前狀態】第 {view['day']} 天，{'夜晚' if view['phase'] == 'night' else '白天'}。")
        lines.append(f"存活：{_seat_list(view, view['alive'])}")
        if view["dead"]:
            lines.append(f"出局：{_seat_list(view, view['dead'])}")
        pv = view["private"]
        if "seer_results" in pv:
            r = "、".join(f"{k}號={'狼人' if v == 'wolf' else '好人'}" for k, v in pv["seer_results"].items()) or "尚無"
            lines.append(f"你的查驗結果：{r}")
        if "antidote" in pv:
            lines.append(f"你的藥：解藥{'還在' if pv['antidote'] else '已用'}、毒藥{'還在' if pv['poison'] else '已用'}")
        if "guard_last" in pv and pv["guard_last"]:
            lines.append(f"你昨晚守了 {pv['guard_last']}號（今晚不能再守他）")
        if self.memory.get("notes"):
            lines.append(f"\n【你自己之前寫下的筆記】\n{self.memory['notes']}")
        if self.skill and self.skill.hook("extra_prompt"):
            extra = self.skill.hook("extra_prompt")(req, view, self.memory)
            if extra:
                lines.append(f"\n【策略提示】\n{extra}")

        kind = req["kind"]
        lines.append(f"\n【你現在要做的事】{KIND_TASK.get(kind, kind)}")
        if kind == "witch":
            info = req["info"]
            if info.get("victim"):
                lines.append(f"今晚被狼人刀的是 {info['victim']}號。" + ("你可以用解藥救他。" if info.get("can_save") else "（你不能救：不能自救）"))
            else:
                lines.append("你看不到今晚的刀口（解藥已用完）。")
            if info.get("can_poison"):
                lines.append(f"可以毒的對象：{_seat_list(view, req['options'])}")
            lines.append('輸出格式：{"thinking": "簡短推理", "save": true 或 false, "poison": 座位號 或 null, "notes": "給自己的筆記(選填)"}')
            lines.append("注意：save 和 poison 同一晚只能用一個。")
        elif kind in SPEECH_KINDS:
            lines.append('輸出格式：{"thinking": "內心推理（只有觀眾看得到）", "speech": "你要說出口的話", '
                         '"claim": {"role": "你公開宣稱的身分(seer/witch/hunter/guard/villager)，沒宣稱就省略", '
                         '"checks": {"座位號": "wolf 或 good"}} 或 null, "notes": "給自己的筆記(選填)"}')
            lines.append("claim 只是幫系統記錄你『嘴上』宣稱了什麼，可以是假的（例如狼人悍跳）。")
        else:
            opts = list(req["options"])
            lines.append(f"可選目標：{_seat_list(view, opts)}")
            none = "，或 null 表示不選" if req["allow_none"] else ""
            lines.append(f'輸出格式：{{"thinking": "簡短推理", "target": 座位號{none}, "notes": "給自己的筆記(選填)"}}')
        return "\n".join(lines)

    # ---------------- act
    def act(self, req: dict, view: dict) -> dict:
        if self.skill and self.skill.hook("decide"):
            r = self.skill.hook("decide")(req, view, self.memory)
            if r:
                return r
        system = self.system_prompt(view)
        user = self.user_prompt(req, view)
        self.last_prompt = (system, user)
        err = None
        for attempt in range(2):
            u = user if not err else user + f"\n\n你上一次的輸出無法解析（{err}），請只輸出一個合法 JSON。"
            raw = llm.chat(self.cfg, system, u)
            try:
                resp = parse_json(raw)
                break
            except ValueError as e:
                err = str(e)
        else:
            raise ValueError(f"LLM 連續輸出非 JSON：{err}")
        if resp.get("notes"):
            self.memory["notes"] = str(resp["notes"])[-1500:]
        if req["kind"] in SPEECH_KINDS and not resp.get("speech"):
            resp["speech"] = resp.get("text") or resp.get("content") or ""
        if "target" in resp and isinstance(resp["target"], str):
            m = re.search(r"\d+", resp["target"])
            resp["target"] = int(m.group()) if m else None
        if req["kind"] == "witch":
            p = resp.get("poison")
            if isinstance(p, str):
                m = re.search(r"\d+", p)
                resp["poison"] = int(m.group()) if m else None
            if isinstance(resp.get("save"), str):
                resp["save"] = resp["save"].lower() in ("true", "yes", "1", "救")
        if self.skill and self.skill.hook("postprocess"):
            resp = self.skill.hook("postprocess")(req, view, resp, self.memory) or resp
        return resp


def parse_json(raw: str) -> dict:
    think = ""
    m = re.search(r"<think>(.*?)</think>", raw, re.S)
    if m:
        think = m.group(1).strip()
        raw = raw[:m.start()] + raw[m.end():]
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("找不到 JSON 物件")
    blob = raw[start:end + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        try:
            obj = json.loads(re.sub(r",\s*([}\]])", r"\1", blob))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失敗：{e}")
    if not isinstance(obj, dict):
        raise ValueError("JSON 不是物件")
    if think and not obj.get("thinking"):
        obj["thinking"] = think[-600:]
    return obj

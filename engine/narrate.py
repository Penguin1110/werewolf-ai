"""把事件轉成中文旁白文字。給 LLM 看的歷史紀錄與網頁的編年史都用這個。"""
from __future__ import annotations

from .roles import role_name

KIND_NAMES = {
    "speech": "白天發言", "wolf_chat": "狼人夜聊", "wolf_kill": "選擇刀人", "seer_check": "查驗",
    "witch": "用藥", "guard": "守護", "vote": "投票", "pk_vote": "PK 投票", "pk_speech": "PK 發言",
    "last_words": "遺言", "hunter_shoot": "開槍",
}


def narrate(ev: dict, game=None) -> str:
    t, d = ev["type"], ev["data"]

    def L(seat):
        if seat is None:
            return "（無）"
        if game is not None:
            return game.p(seat).label()
        return f"{seat}號"

    if t == "game_start":
        return f"遊戲開始：{d['board_name']}，共 {len(d['players'])} 名玩家。"
    if t == "role_assign":
        return "身分分配：" + "、".join(f"{s}號={role_name(r)}" for s, r in d["roles"].items())
    if t == "your_role":
        s = f"你的身分是【{role_name(d['role'])}】。"
        if d.get("teammates"):
            s += "你的狼隊友是：" + "、".join(L(x) for x in d["teammates"]) + "。"
        return s
    if t == "phase":
        return f"—— 第 {d['day']} 夜，天黑請閉眼 ——" if d["phase"] == "night" else f"—— 第 {d['day']} 天，天亮了 ——"
    if t == "acting":
        return f"{L(d['seat'])} 正在思考（{KIND_NAMES.get(d['kind'], d['kind'])}）…"
    if t == "thought":
        return f"{L(d['seat'])} 的內心：{d['text']}"
    if t == "fallback":
        return f"⚠ {L(d['seat'])} 的 AI 回應無效，改用預設策略：{d['error']}"
    if t == "guard":
        return f"守衛 {L(d['seat'])} 守護了 {L(d['target'])}。" if d["target"] else f"守衛 {L(d['seat'])} 今晚空守。"
    if t == "wolf_chat":
        return f"[狼人頻道] {L(d['seat'])}：{d['text']}"
    if t == "wolf_vote":
        return f"[狼人頻道] {L(d['seat'])} 想刀 {L(d['target'])}。"
    if t == "wolf_kill":
        return f"[狼人頻道] 狼人決定今晚刀 {L(d['target'])}。"
    if t == "seer_check":
        return f"預言家 {L(d['seat'])} 查驗 {L(d['target'])}：{'狼人' if d['result'] == 'wolf' else '好人'}。"
    if t == "witch_info":
        return f"女巫得知今晚被刀的是 {L(d['victim'])}。" if d["victim"] else "女巫今晚看不到刀口（解藥已用）。"
    if t == "witch":
        if d["save"]:
            return f"女巫 {L(d['seat'])} 使用解藥救了 {L(d['save'])}。"
        if d["poison"]:
            return f"女巫 {L(d['seat'])} 使用毒藥毒了 {L(d['poison'])}。"
        return f"女巫 {L(d['seat'])} 今晚沒有用藥。"
    if t == "night_result":
        if not d["deaths"]:
            return "昨晚是平安夜，沒有人死亡。"
        return "昨晚死亡的是：" + "、".join(L(s) for s in d["deaths"]) + "。"
    if t == "death":
        return {"night": f"{L(d['seat'])} 在夜裡出局了。", "exile": f"{L(d['seat'])} 被放逐出局。",
                "shot": f"{L(d['seat'])} 被獵人帶走。"}.get(d["public_cause"], f"{L(d['seat'])} 出局。")
    if t == "death_detail":
        cause = {"wolf": "被狼人刀殺", "poison": "被女巫毒殺", "exile": "被投票放逐", "shot": "被獵人射殺"}[d["cause"]]
        return f"（上帝視角）{L(d['seat'])} 的真實身分是{role_name(d['role'])}，死因：{cause}。"
    if t == "last_words":
        return f"{L(d['seat'])} 的遺言：{d['text']}"
    if t == "hunter_shoot":
        return f"獵人 {L(d['seat'])} 開槍帶走了 {L(d['target'])}！" if d["target"] else f"{L(d['seat'])} 選擇不開槍。"
    if t == "speech_order":
        return "發言順序：" + " → ".join(str(s) for s in d["order"])
    if t == "speech":
        return f"{'[PK] ' if d.get('pk') else ''}{L(d['seat'])}：{d['text']}"
    if t == "vote":
        return f"{L(d['seat'])} 投給 {L(d['target'])}。" if d["target"] else f"{L(d['seat'])} 棄票。"
    if t == "vote_result":
        tally = "，".join(f"{s}號 {c} 票" for s, c in sorted(d["tally"].items(), key=lambda x: -x[1]))
        if d["exiled"]:
            return f"投票結果：{tally}。{L(d['exiled'])} 被放逐。"
        if d["tie"]:
            return f"投票結果：{tally}。" + "、".join(f"{s}號" for s in d["tie"]) + " 平票，進入 PK。"
        return "所有人棄票，今天無人出局。"
    if t == "pk_start":
        return "PK 台上：" + "、".join(L(s) for s in d["candidates"]) + "，請依序發言。"
    if t == "no_exile":
        return d["reason"]
    if t == "game_over":
        w = {"wolf": "狼人陣營勝利！", "village": "好人陣營勝利！", None: "遊戲結束（無勝者）"}[d["winner"]]
        return f"🏁 {w} 原因：{d['reason']}"
    return f"{t}: {d}"

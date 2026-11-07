"""範例：每次決策前，自動把公開的票型、對跳、查驗整理成表格交給 LLM。"""
from collections import defaultdict


def extra_prompt(request, view, memory):
    votes = defaultdict(list)
    claims = {}
    for ev in view["history"]:
        d = ev["data"]
        if ev["type"] == "vote":
            votes[ev["day"]].append((d["seat"], d["target"]))
        if ev["type"] in ("speech", "last_words") and d.get("claim"):
            claims[d["seat"]] = d["claim"]
    lines = []
    for day, vs in sorted(votes.items()):
        s = "，".join(f"{a}→{b if b else '棄'}" for a, b in vs)
        lines.append(f"第{day}天票型：{s}")
        # 跟票分析
        groups = defaultdict(list)
        for a, b in vs:
            groups[b].append(a)
        for b, voters in groups.items():
            if b and len(voters) >= 2:
                lines.append(f"  投 {b}號 的集團：{voters}")
    for s, c in claims.items():
        if c.get("role"):
            ck = "，".join(f"{k}號={'狼' if v == 'wolf' else '好'}" for k, v in (c.get("checks") or {}).items())
            lines.append(f"{s}號宣稱{c['role']}" + (f"（報：{ck}）" if ck else ""))
    if not lines:
        return None
    return "（名偵探自動整理的證據）\n" + "\n".join(lines)

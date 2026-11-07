"""範例：用程式碼幫 LLM 做「帳本」，把自己之前報過的假查驗記下來，避免前後矛盾。"""


def postprocess(request, view, response, memory):
    claim = response.get("claim") if isinstance(response, dict) else None
    if view["role"] == "werewolf" and isinstance(claim, dict) and claim.get("role") == "seer":
        book = memory.setdefault("fake_checks", {})
        for k, v in (claim.get("checks") or {}).items():
            book.setdefault(str(k), v)
    return response


def extra_prompt(request, view, memory):
    if view["role"] == "werewolf" and memory.get("fake_checks"):
        items = "、".join(f"{k}號={'查殺' if v == 'wolf' else '金水'}" for k, v in memory["fake_checks"].items())
        return f"你之前（假裝預言家）已經報過：{items}。今天的說法必須和這些一致，再加一個新的查驗。"
    return None

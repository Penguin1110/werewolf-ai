"""（選填）用程式碼寫的策略。三個函式都可以不寫，寫了就會被呼叫。

request = {"kind": "...", "options": [座位...], "allow_none": bool, "info": {...}}
view    = 你的視角，常用欄位：
          view["seat"] 你的座位, view["role"] 你的身分, view["day"] 第幾天,
          view["alive"] 存活座位, view["teammates"] 狼隊友（狼人才有）,
          view["private"]["seer_results"] 查驗結果（預言家）,
          view["history"] 你看得到的所有事件（每個都有 type / data / text）
memory  = 一個 dict，整場遊戲都會保留，可以存任何東西。
"""


def on_game_start(view, memory):
    memory["my_role"] = view["role"]


def decide(request, view, memory):
    """回傳 dict 就會「直接取代」AI 的決定；回傳 None 就交給 LLM / 規則 AI。

    例：女巫第一晚一定救人
    """
    if request["kind"] == "witch" and view["day"] == 1 and request["info"].get("can_save"):
        return {"save": True, "poison": None, "thinking": "（硬規則）首夜必救。"}
    return None


def extra_prompt(request, view, memory):
    """回傳一段文字，會附加在給 LLM 的提示最後面。可以放即時計算的情報。"""
    return None


def postprocess(request, view, response, memory):
    """拿到 LLM 的回應後還可以再修改。回傳修改後的 response。"""
    return response

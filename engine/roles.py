"""角色與板子定義。"""
from __future__ import annotations

ROLES = {
    "werewolf": {"name": "狼人", "team": "wolf", "god": False,
                 "desc": "每晚與狼隊友討論並刀殺一名玩家。白天隱藏身分、誤導好人。"},
    "villager": {"name": "村民", "team": "village", "god": False,
                 "desc": "沒有技能。靠發言與投票找出狼人。"},
    "seer": {"name": "預言家", "team": "village", "god": True,
             "desc": "每晚查驗一名玩家，得知他是「好人」還是「狼人」。"},
    "witch": {"name": "女巫", "team": "village", "god": True,
              "desc": "有一瓶解藥（救當晚被刀的人）和一瓶毒藥（毒死一人），同一晚只能用一瓶，不能自救。"},
    "hunter": {"name": "獵人", "team": "village", "god": True,
               "desc": "被狼刀或被放逐出局時可以開槍帶走一人；被女巫毒死則不能開槍。"},
    "guard": {"name": "守衛", "team": "village", "god": True,
              "desc": "每晚守護一人免於狼刀，不能連續兩晚守同一人。若同守同救，該玩家仍會死亡（奶穿）。"},
}

BOARDS = {
    "6": {"name": "6 人速戰局", "roles": ["werewolf"] * 2 + ["villager"] * 2 + ["seer", "witch"]},
    "9": {"name": "9 人預女獵", "roles": ["werewolf"] * 3 + ["villager"] * 3 + ["seer", "witch", "hunter"]},
    "12": {"name": "12 人預女獵守", "roles": ["werewolf"] * 4 + ["villager"] * 4 + ["seer", "witch", "hunter", "guard"]},
}

ROLE_ALIASES = {
    "werewolf": ["狼人", "狼", "werewolf", "wolf"],
    "villager": ["村民", "平民", "villager"],
    "seer": ["預言家", "预言家", "seer"],
    "witch": ["女巫", "witch"],
    "hunter": ["獵人", "猎人", "hunter"],
    "guard": ["守衛", "守卫", "guard"],
}


def role_name(role: str) -> str:
    return ROLES[role]["name"]


def team_of(role: str) -> str:
    return ROLES[role]["team"]

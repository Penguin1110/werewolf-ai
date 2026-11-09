# 🌙 月下狼人殺 · AI 競技場

讓每個人寫自己的**策略 Skill**，裝到自己的 AI 玩家上，在你的電腦上打一場完整的狼人殺，
然後用帶有遊戲美術風格的畫面一步一步看每個 AI 說了什麼、投了誰、晚上做了什麼，還有它們的**內心獨白**。

- **零安裝**：只用 Python 標準函式庫（3.9 以上），不需要 `pip install`。
- **全部在本機**：遊戲引擎、網頁、回放都在你的電腦上跑，AI 玩家統一呼叫 OpenAI GPT API。
- **沒有 LLM 也能玩**：內建「規則 AI」，離線就能跑完整對局（也當 LLM 出錯時的備援）。
- **混戰**：每個座位可以選不同的 skill 和不同的 GPT 模型。

---

## 1. 快速開始

```bash
cd werewolf-ai
python run.py
```

瀏覽器會自動打開 `http://localhost:8765`（沒有的話手動打開）。

1. 在**大廳**選板子（6 / 9 / 12 人）、每個座位的名字、策略 Skill、模型
2. 按「⚔ 開始對局」（記得先設定好 OpenAI 金鑰，見第 2 節）
3. 觀戰：

| 按鍵 / 按鈕 | 功能 |
|---|---|
| 點擊戰場 / 點對話框 | 下一步（預設為手動單步） |
| `空白鍵` / ▶ | 開始自動播放 / 暫停 |
| `→` / ⏭ | 下一步 |
| ⏮ | 從頭重播 |
| 0.5× ~ ⚡ | 播放速度 |
| 👁 上帝視角（`g`） | 打開：看得到所有身分、夜晚行動、狼人頻道、每個 AI 的內心獨白；關閉：只看得到公開資訊（像一般玩家） |
| 📜 編年史（`l`） | 完整文字紀錄，**點任何一行就能跳到那個時間點** |
| 點對話框 | 立刻顯示完整句子 / 下一步 |

每局結束會自動存到 `replays/`，大廳右邊可以點來重看，也可以把回放 `.json` 傳給朋友，用「📂 載入回放檔」打開。
手動單步時，AI 的內心思考會保留在畫面上，直到你再次點擊。勝負確定後會先公開身分，讓每位 AI 依序進行賽後復盤，再顯示結算畫面；若不需要，可在 `config.json` 的 `rules` 設定 `"postgame_discussion": false`。

只想在終端機跑：

```bash
python run.py --headless --god          # 跑一局並印出上帝視角紀錄
python run.py --headless --board 12 --seed 42
```

---

## 2. 設定 OpenAI API（統一使用 GPT）

所有 AI 玩家統一走 OpenAI 的 **Chat Completions API**（`https://api.openai.com/v1/chat/completions`）。

**放金鑰（二選一）**

```bash
# 方法 A：在專案資料夾建立 .env（最方便，已在 .gitignore 裡，不會被 commit）
cp .env.example .env      # 然後把 sk-... 貼進去

# 方法 B：環境變數
export OPENAI_API_KEY=sk-...          # macOS / Linux
$env:OPENAI_API_KEY="sk-..."          # Windows PowerShell
```

啟動 `python run.py` 時終端機和大廳都會顯示有沒有讀到金鑰。沒有金鑰時只能選「規則 AI」。

**可選的模型**（`config.json` 的 `models`，大廳下拉選單可以每個座位分開選）：

| 設定名稱 | 說明 |
|---|---|
| `gpt-6-luna` | 預設。GPT-6 系列最便宜、最快，適合大量對局 |
| `gpt-6.1-terra` | 快速、效率好，寫作自然 |
| `gpt-6.1-sol` | 接近 Astra 的能力、價格較低 |
| `gpt-6-astra` | 最強也最貴 |
| `rule` | 不呼叫 API 的內建規則 AI（免費、離線、測試 skill 流程用） |

想加別的 GPT 模型，照格式多加一行就好：

```json
"gpt-5.5": {"provider": "openai", "model": "gpt-5.5", "label": "GPT-5.5"}
```

**共用設定**（`config.json` 的 `openai` 區塊，套用到所有 GPT 模型；單一模型也可以個別覆蓋）：

| 欄位 | 預設 | 說明 |
|---|---|---|
| `reasoning_effort` | `low` | 推理強度：`none` / `low` / `medium` / `high` / `xhigh` / `max`。越高越聰明但越慢越貴 |
| `max_completion_tokens` | `4000` | 包含推理用的 token。如果出現「輸出被截斷」就調高 |
| `json_mode` | `true` | 要求模型一定輸出 JSON |
| `temperature` | 不送 | 推理模型通常不支援；有設定但模型不支援時會自動拿掉 |
| `base_url` | OpenAI 官方 | 用公司 / 學校的 OpenAI 相容代理時才改 |
| `api_key_env` | `OPENAI_API_KEY` | 從哪個環境變數讀金鑰 |

一局 9 人大約 60~90 次 API 呼叫。API 偶爾出錯（429 限流、5xx）會自動重試；回應無法解析時會再問一次，還是不行才由規則 AI 代打，並在編年史標示 ⚠。

---

## 3. 寫你自己的策略 Skill（重點！）

一個 Skill 就是 `skills/` 底下的一個資料夾：

```
skills/
  xiaoming/            ← 資料夾名稱 = skill ID
    SKILL.md           ← 必填：用中文寫給 AI 看的策略
    strategy.py        ← 選填：用 Python 寫硬規則 / 動態情報
```

最快的方法：**複製 `skills/_template/` 改名**，重新整理大廳就會出現。

也可以在大廳的「策略 Skill 圖鑑」按 **📦 匯入外部 Skill（ZIP）**。ZIP 裡可以直接放
`SKILL.md` / `strategy.py`，或用一層以 Skill ID 命名的資料夾包住它們。既有 Skill 不會被覆蓋。
外部 `strategy.py` 會以本機 Python 權限執行，請只匯入可信來源。
每個玩家席位也有自己的 **＋ Skill** 按鈕；從該按鈕匯入後，新 Skill 會直接套用到那名玩家。
所有座位預設使用 `baseline`（大廳顯示為「一般模式」），仍可從各自的下拉選單改用不同策略。

### 3.1 `SKILL.md`

```markdown
---
name: 小明的鐵血預言家
author: 小明
description: 一句話介紹，顯示在大廳
persona: 講話很衝、喜歡用反問句
rule_fake_claim: 0.5        # 用「規則 AI」時，狼人悍跳的機率
---

## 通用
所有身分都看得到的策略……

## 好人
村民、預言家、女巫、獵人、守衛都看得到……

## 狼人
只有拿到狼人時才看得到……

## 預言家 / ## 女巫 / ## 獵人 / ## 守衛 / ## 村民
各身分專屬策略……
```

AI 拿到哪個身分，就只會看到「沒有標題的段落 + 通用 + (好人) + 該身分段落」，會被放進系統提示的「策略手冊」區，
並被要求**優先遵守**。所以你寫得越具體（什麼情況 → 做什麼），AI 越聽話。

### 3.2 `strategy.py`（進階）

四個函式都是選填，寫了就會被呼叫：

```python
def on_game_start(view, memory): ...
def decide(request, view, memory):      # 回傳 dict = 直接替 AI 做決定；回傳 None = 交給 LLM
def extra_prompt(request, view, memory):  # 回傳字串，會附加到給 LLM 的提示
def postprocess(request, view, response, memory):  # 修改 LLM 的回應
```

用途舉例（都在範例 skill 裡）：
- `_template`：女巫首夜**一定**救人（硬規則，不靠 LLM）
- `detective`：自動整理每天的**票型**與**跳身分紀錄**丟給 LLM 當推理線索
- `bold_wolf`：幫悍跳的狼記住自己報過的假查驗，避免前後矛盾

`memory` 是整場遊戲都會保留的 dict，可以存任何東西。

> ⚠ `strategy.py` 是真的 Python 程式，會在你的電腦上執行。收別人的 skill 之前先看一下內容。

### 3.3 `request` 與回應格式

| `request["kind"]` | 時機 | 要回傳 |
|---|---|---|
| `speech` | 白天輪流發言 | `{"speech": "...", "claim": {...}?}` |
| `pk_speech` | 平票 PK 發言 | 同上 |
| `last_words` | 出局遺言 | 同上 |
| `wolf_chat` | 夜晚狼人頻道（只有狼看得到） | `{"speech": "..."}` |
| `wolf_kill` | 狼人選刀口（多數決） | `{"target": 座位}` |
| `seer_check` | 預言家查驗 | `{"target": 座位}` |
| `witch` | 女巫用藥，`request["info"]` 有 `victim`、`can_save`、`can_poison` | `{"save": bool, "poison": 座位或 None}` |
| `guard` | 守衛守護（可空守） | `{"target": 座位或 None}` |
| `vote` / `pk_vote` | 投票放逐（可棄票） | `{"target": 座位或 None}` |
| `hunter_shoot` | 獵人開槍（可不開） | `{"target": 座位或 None}` |
| `postgame` | 身分公開後的賽後復盤 | `{"speech": "賽後感想或檢討"}` |

- `request["options"]` 是合法目標（**每次都隨機打亂順序**，避免 LLM 總是選第一個）。
- 任何回應都可以多帶 `"thinking"`（內心獨白，只有上帝視角看得到）和 `"notes"`（給自己的筆記，下次決策時會再看到）。
- `claim` 是「嘴上宣稱」的身分與查驗，例如 `{"role": "seer", "checks": {"5": "wolf"}}`，可以是假的。沒給的話引擎會從發言文字自動抽取。
- 不合法的回應（選了不能選的人、JSON 壞掉…）會被引擎擋下，改用規則 AI 代打。

### 3.4 `view`（你的視角）

```python
view = {
  "seat": 3, "name": "老王", "role": "witch", "role_name": "女巫", "team": "village",
  "day": 2, "phase": "night",
  "alive": [1, 2, 3, ...], "dead": [5],
  "players": [{"seat": 1, "name": "阿明", "alive": True}, ...],
  "teammates": [2, 7],                    # 只有狼人才有
  "private": {"seer_results": {4: "good"},   # 預言家
              "antidote": False, "poison": True,  # 女巫
              "guard_last": 6},            # 守衛
  "history": [ {"type": "speech", "day": 1, "data": {...}, "text": "3號老王：..."}, ... ],
}
```

`history` 只包含**你有權知道**的事件（資訊隔離），常用的 `type`：
`phase`、`night_result`、`death`、`speech`、`last_words`、`vote`、`vote_result`、`hunter_shoot`、
狼人才看得到的 `wolf_chat` / `wolf_vote` / `wolf_kill`、預言家的 `seer_check`、女巫的 `witch_info` / `witch`、守衛的 `guard`。

---

## 4. 策略擂台：比勝率

```bash
python tournament.py --games 30 --model rule          # 免費：全部用規則 AI，先確認 skill 程式沒問題
python tournament.py --games 20 --model gpt-6-luna    # 全部用同一個 GPT 模型，只比 skill 的差異
python tournament.py --games 50                       # 用 config.json 各座位自己的模型
python tournament.py --games 20 --board 12 --save-replays --out result.json
```

> 用 GPT 跑擂台會花 API 費用：20 局 × 約 80 次呼叫 = 約 1600 次呼叫，建議先用 `gpt-6-luna`。

每局身分重新隨機分配、座位輪轉，最後輸出每個 skill 的總勝率、好人/狼人陣營勝率、各身分勝率、存活率。

> 內建的規則 AI 很陽春（好人很容易被悍跳騙），所以純規則 AI 對打時狼人勝率偏高。
> 這正好是給大家的挑戰：寫一個能讓好人翻盤的 skill。

---

## 5. 遊戲規則

| 板子 | 配置 |
|---|---|
| 6 人速戰局 | 2 狼、2 村民、預言家、女巫 |
| 9 人預女獵 | 3 狼、3 村民、預言家、女巫、獵人 |
| 12 人預女獵守 | 4 狼、4 村民、預言家、女巫、獵人、守衛 |

- 夜晚順序：守衛 → 狼人（先夜聊再投票決定刀口）→ 預言家 → 女巫
- 女巫：解藥、毒藥各一瓶，同一晚只能用一瓶，**不能自救**；解藥用掉後看不到刀口
- 守衛：不能連續兩晚守同一人；**同守同救 = 奶穿**（照樣死）
- 獵人：被刀或被放逐可開槍；**被毒不能開槍**
- 首夜死者有遺言；之後只有被放逐 / 被槍殺的人有遺言
- 白天投票平票 → 平票者 PK 發言 → 其他人再投一次 → 仍平票則無人出局
- 死亡不公開身分
- 勝負**屠邊**：狼全滅好人勝；神職全滅或村民全滅狼人勝
- `config.json` 可加 `"rules": {"majority_win": true}`（狼數 ≥ 好人數就直接獲勝）、`max_days`、`speech_max_chars` 等

---

## 6. 專案結構

```
werewolf-ai/
├── run.py              本機伺服器 + headless 模式
├── tournament.py       策略擂台
├── config.json         GPT 模型與座位設定
├── .env.example        放 OpenAI 金鑰的範例
├── engine/
│   ├── game.py         主持人：流程、規則、資訊隔離、驗證
│   ├── agents.py       LLMAgent（提示詞）與 RuleAgent（規則 AI）
│   ├── llm.py          零依賴 OpenAI Chat Completions 呼叫
│   ├── skill.py        Skill 載入器
│   ├── claims.py       從發言抽取跳身分 / 查驗
│   ├── narrate.py      事件 → 中文旁白
│   └── roles.py        角色與板子
├── skills/             大家的策略都放這
├── web/                遊戲畫面（純 HTML/CSS/JS，美術全部由程式產生的 SVG）
└── replays/            自動存的回放
```

想加新角色（例如白痴、狼王）：在 `roles.py` 加角色與板子、在 `game.py` 的 `night()` / `kill()` 加技能邏輯、在 `web/art.js` 加徽章圖示。

---

## 7. 參考的開源專案與研究

設計上參考了這些專案的做法：

- **Werewolf Arena**（Google Research, 2024）— 用狼人殺評測 LLM；投票與技能選項**隨機排序**避免位置偏誤。https://github.com/google/werewolf_arena
- **AIWolf / AIWolfDial** — 日本從 2014 年起的 AI 狼人殺競賽，嚴格的伺服器端**資訊隔離**、Agent 透過協定連線。https://aiwolfdial.github.io/aiwolf-nlp/en
- **Exploring LLMs for Communication Games: Werewolf**（xuyuzhuang11/Werewolf）— 不微調、靠提示詞與經驗讓 LLM 玩狼人殺。https://github.com/xuyuzhuang11/Werewolf
- **LLMWereWolf**（Mai0313）— 抽象 LLM 介面、事件系統。https://github.com/Mai0313/LLMWereWolf
- **zhulin025/werewolf-game** — 中文 12 人局、屠邊、女巫雙藥互斥、守衛連守限制、Agent 超時自動由 Bot 代打。https://github.com/zhulin025/werewolf-game
- **deepwolf** — 固定 seed 可重現、不合法行動由引擎驗證、離線 mock。https://github.com/JuneQQQ/deepwolf

本專案程式碼與美術皆為原創，未複製上述專案的程式碼。

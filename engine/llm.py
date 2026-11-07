"""OpenAI GPT 呼叫（只用 Python 標準函式庫）。

統一使用 OpenAI Chat Completions API：POST {base_url}/chat/completions
金鑰從環境變數 OPENAI_API_KEY 讀取（也可以寫在專案根目錄的 .env 檔）。

provider = "openai"  GPT 模型
provider = "rule"    不呼叫 API，用內建規則 AI（沒有金鑰 / 離線時使用）
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASE_URL = "https://api.openai.com/v1"


class LLMError(Exception):
    pass


_UNSUPPORTED: Dict[str, set] = {}  # 模型 -> 已知不支援的參數，避免每次都多打一次 400


def load_dotenv(path: str = os.path.join(ROOT, ".env")):
    """讀取專案根目錄的 .env（格式：OPENAI_API_KEY=sk-...），不覆蓋已存在的環境變數。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()


def api_key(cfg: Dict) -> str:
    if cfg.get("api_key"):
        return cfg["api_key"]
    env = cfg.get("api_key_env", "OPENAI_API_KEY")
    return os.environ.get(env, "")


def check_ready(cfg: Dict):
    """開局前檢查金鑰，避免整局都在用備援 AI。"""
    if cfg.get("provider", "openai") == "rule":
        return
    if not api_key(cfg):
        env = cfg.get("api_key_env", "OPENAI_API_KEY")
        raise LLMError(f"找不到 OpenAI API 金鑰。請設定環境變數 {env}，"
                       f"或在專案資料夾建立 .env 檔，內容寫一行：{env}=sk-...")


def _post(url: str, headers: Dict[str, str], body: Dict, timeout: float) -> Dict:
    last = None
    bad = _UNSUPPORTED.setdefault(body.get("model", ""), set())
    body = {k: v for k, v in body.items() if k not in bad}
    for attempt in range(4):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")[:600]
            last = LLMError(f"HTTP {e.code}: {msg}")
            if e.code == 400:
                # 有些模型不支援某些參數（例如 temperature），自動拿掉再試一次
                m = re.search(r"[Uu]nsupported (?:parameter|value)[^']*'([a-z_]+)'", msg) or \
                    re.search(r"'([a-z_]+)' (?:is not supported|does not support)", msg)
                if m and m.group(1) in body and m.group(1) not in ("model", "messages"):
                    bad.add(m.group(1))
                    body = {k: v for k, v in body.items() if k != m.group(1)}
                    continue
                raise last
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            raise last
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = LLMError(f"連線失敗（{url}）：{e}")
            time.sleep(1.5 * (attempt + 1))
    raise last


def chat(cfg: Dict, system: str, user: str) -> str:
    if cfg.get("provider", "openai") != "openai":
        raise LLMError(f"不支援的 provider：{cfg.get('provider')}（本專案統一使用 openai）")
    check_ready(cfg)
    url = cfg.get("base_url", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key(cfg)}"}
    body = {"model": cfg["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if cfg.get("reasoning_effort"):
        body["reasoning_effort"] = cfg["reasoning_effort"]
    if cfg.get("max_completion_tokens", 4000):
        body["max_completion_tokens"] = cfg.get("max_completion_tokens", 4000)
    if cfg.get("temperature") is not None:
        body["temperature"] = cfg["temperature"]
    if cfg.get("json_mode", True):
        body["response_format"] = {"type": "json_object"}
    body.update(cfg.get("extra", {}))
    res = _post(url, headers, body, float(cfg.get("timeout", 180)))
    try:
        choice = res["choices"][0]
        content = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"回應格式不對：{str(res)[:300]}")
    if not content and choice.get("finish_reason") == "length":
        raise LLMError("輸出被截斷（推理用掉太多 token），請調高 max_completion_tokens 或降低 reasoning_effort")
    return content

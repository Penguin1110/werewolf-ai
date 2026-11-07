#!/usr/bin/env python3
"""AI 狼人殺 — 本機伺服器。

    python run.py              # 開啟 http://localhost:8765 ，在網頁大廳設定玩家並開局
    python run.py --port 9000
    python run.py --headless   # 不開網頁，直接在終端機跑一局並存成回放檔

只用 Python 標準函式庫，不需要 pip install。
"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from engine.factory import REPLAY_DIR, SKILLS_DIR, create_game, load_config, save_replay  # noqa: E402
from engine.roles import BOARDS, ROLES  # noqa: E402
from engine.skill import list_skills  # noqa: E402
from engine.llm import api_key  # noqa: E402

WEB_DIR = os.path.join(ROOT, "web")
GAMES = {}
LOCK = threading.Lock()
MAX_SKILL_ZIP_BYTES = 2 * 1024 * 1024
MAX_SKILL_UNPACKED_BYTES = 5 * 1024 * 1024


def import_skill_zip(data: bytes, filename: str, skills_dir: str = SKILLS_DIR) -> str:
    """安全地把單一 Skill ZIP 安裝到 skills/，不覆蓋既有資料夾。"""
    if not filename.lower().endswith(".zip"):
        raise ValueError("請選擇 .zip 格式的 Skill 壓縮檔")
    if not data:
        raise ValueError("ZIP 檔案是空的")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("檔案不是有效的 ZIP") from e

    infos = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
    if not infos or len(infos) > 100:
        raise ValueError("ZIP 必須包含 1 到 100 個檔案")
    if sum(i.file_size for i in infos) > MAX_SKILL_UNPACKED_BYTES:
        raise ValueError("Skill 解壓後不可超過 5 MB")

    clean = {}
    for info in infos:
        name = info.filename.replace("\\", "/")
        parts = [p for p in name.split("/") if p not in ("", ".")]
        if not parts or ".." in parts or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            raise ValueError("ZIP 內含不安全的路徑")
        if info.flag_bits & 1:
            raise ValueError("不支援加密的 ZIP")
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError("ZIP 不可包含符號連結")
        clean[info] = parts

    manifests = [(info, parts) for info, parts in clean.items() if parts[-1].lower() == "skill.md"]
    if len(manifests) != 1:
        raise ValueError("ZIP 必須包含且只能包含一個 SKILL.md")
    _, manifest_parts = manifests[0]
    base = manifest_parts[:-1]
    if len(base) > 1:
        raise ValueError("SKILL.md 必須位於 ZIP 根目錄或第一層 Skill 資料夾")
    skill_id = base[0] if base else os.path.splitext(os.path.basename(filename))[0]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", skill_id):
        raise ValueError("Skill ID 只能使用英文字母、數字、底線與連字號")

    selected = []
    for info, parts in clean.items():
        if base:
            if parts[:1] != base:
                continue
            relative = parts[1:]
        else:
            relative = parts
        if relative:
            selected.append((info, relative))
    if not selected:
        raise ValueError("ZIP 中找不到 Skill 內容")

    os.makedirs(skills_dir, exist_ok=True)
    target = os.path.join(skills_dir, skill_id)
    if os.path.exists(target):
        raise ValueError(f"Skill ID「{skill_id}」已存在，請先改名")
    staging = tempfile.mkdtemp(prefix=".skill-import-", dir=skills_dir)
    try:
        for info, relative in selected:
            out = os.path.abspath(os.path.join(staging, *relative))
            if os.path.commonpath((os.path.abspath(staging), out)) != os.path.abspath(staging):
                raise ValueError("ZIP 內含不安全的路徑")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with zf.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
        manifest = os.path.join(staging, "SKILL.md")
        if not os.path.isfile(manifest):
            raise ValueError("找不到 SKILL.md")
        with open(manifest, encoding="utf-8") as f:
            f.read()
        os.replace(staging, target)
        staging = ""
    finally:
        zf.close()
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging)
    return skill_id


class LiveGame:
    def __init__(self, game, meta):
        self.id = uuid.uuid4().hex[:10]
        self.game = game
        self.meta = meta
        self.done = False
        self.error = None
        self.replay_file = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            self.game.run()
        except Exception as e:
            traceback.print_exc()
            self.error = f"{type(e).__name__}: {e}"
        finally:
            try:
                self.replay_file = os.path.basename(save_replay(self.game, self.meta))
            except Exception:
                traceback.print_exc()
            self.done = True


def model_labels(models):
    return [{"id": k, "label": v.get("label", k), "provider": v.get("provider", "rule")}
            for k, v in models.items() if not k.startswith("_")]


class Handler(BaseHTTPRequestHandler):
    server_version = "WerewolfAI/1.0"

    def log_message(self, fmt, *args):
        message = fmt % args
        if "/api/events" not in message:
            sys.stderr.write("[web] " + message + "\n")

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}

    def _raw_body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            raise ValueError("沒有收到檔案")
        if n > limit:
            raise ValueError(f"檔案不可超過 {limit // (1024 * 1024)} MB")
        return self.rfile.read(n)

    # ---------------------------------------------------------------- GET
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        try:
            if path == "/api/setup":
                cfg = load_config()
                return self._json({
                    "board": cfg.get("board", "9"), "players": cfg["players"],
                    "models": model_labels(cfg["models"]),
                    "skills": [s.info() for s in list_skills(SKILLS_DIR)],
                    "boards": {k: {"name": v["name"], "roles": v["roles"]} for k, v in BOARDS.items()},
                    "roles": ROLES,
                    "openai_key": bool(api_key(cfg.get("openai", {}))),
                    "key_env": cfg.get("openai", {}).get("api_key_env", "OPENAI_API_KEY"),
                })
            if path.startswith("/api/events/"):
                gid = path.split("/")[-1]
                lg = GAMES.get(gid)
                if not lg:
                    return self._json({"error": "找不到這場遊戲"}, 404)
                since = int(parse_qs(url.query).get("since", ["0"])[0])
                evs = lg.game.events[since:]
                return self._json({"events": evs, "done": lg.done, "error": lg.error, "replay": lg.replay_file})
            if path == "/api/replays":
                os.makedirs(REPLAY_DIR, exist_ok=True)
                items = []
                for f in sorted(os.listdir(REPLAY_DIR), reverse=True):
                    if f.endswith(".json"):
                        items.append({"file": f, "size": os.path.getsize(os.path.join(REPLAY_DIR, f))})
                return self._json(items[:200])
            if path.startswith("/api/replays/"):
                name = os.path.basename(path.split("/api/replays/")[1])
                fp = os.path.join(REPLAY_DIR, name)
                if not os.path.exists(fp):
                    return self._json({"error": "not found"}, 404)
                with open(fp, encoding="utf-8") as f:
                    return self._json(json.load(f))
            return self._static(path)
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": str(e)}, 500)

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if not fp.startswith(WEB_DIR) or not os.path.isfile(fp):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ---------------------------------------------------------------- POST
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/skills/import":
                filename = unquote(self.headers.get("X-Skill-Filename", "skill.zip"))
                data = self._raw_body(MAX_SKILL_ZIP_BYTES)
                skill_id = import_skill_zip(data, filename)
                return self._json({"ok": True, "skill_id": skill_id})
            if path == "/api/start":
                body = self._body()
                cfg = load_config()
                board = str(body.get("board") or cfg.get("board", "9"))
                players = body.get("players") or cfg["players"]
                seed = body.get("seed")
                seed = int(seed) if seed not in (None, "") else None
                game = create_game(players, cfg["models"], board=board, seed=seed, rules=cfg.get("rules"))
                lg = LiveGame(game, {"players": players[:len(BOARDS[board]["roles"])], "board": board})
                with LOCK:
                    GAMES[lg.id] = lg
                lg.thread.start()
                return self._json({"game_id": lg.id, "seed": game.seed})
            if path.startswith("/api/stop/"):
                lg = GAMES.get(path.split("/")[-1])
                if lg:
                    lg.game.abort()
                return self._json({"ok": True})
            return self._json({"error": "unknown endpoint"}, 404)
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": f"{type(e).__name__}: {e}"}, 400)


def headless(args):
    cfg = load_config(args.config)
    board = args.board or cfg.get("board", "9")

    def show(ev):
        if ev["type"] in ("acting",):
            return
        if ev["vis"] == "all" or args.god:
            prefix = "" if ev["vis"] == "all" else "  · "
            print(prefix + ev["text"], flush=True)

    game = create_game(cfg["players"], cfg["models"], board=board, seed=args.seed, on_event=show, rules=cfg.get("rules"))
    game.run()
    path = save_replay(game, {"players": cfg["players"], "board": board})
    print(f"\n回放已存到：{path}")


def main():
    ap = argparse.ArgumentParser(description="AI 狼人殺")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--headless", action="store_true", help="只在終端機跑一局")
    ap.add_argument("--god", action="store_true", help="headless 模式下顯示上帝視角")
    ap.add_argument("--board", default=None, choices=list(BOARDS))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.headless:
        return headless(args)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"🐺 AI 狼人殺已啟動：{url}  （Ctrl+C 結束）")
    ocfg = load_config(args.config).get("openai", {})
    if api_key(ocfg):
        print("✅ 已讀到 OpenAI API 金鑰")
    else:
        print(f"⚠ 沒有讀到 OpenAI API 金鑰（{ocfg.get('api_key_env', 'OPENAI_API_KEY')}），目前只能用「規則 AI」。")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n掰掰！")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
导航站服务：提供 index.html 等静态文件，并把导航数据保存为 data.json。

- 只用 Python 标准库，兼容 Python 3.6+（含 CentOS 7 自带的 3.6），无需安装任何依赖。
- 每次保存前自动把旧版本复制到备份目录，默认保留最近 100 份。
- 写入先写临时文件再原子替换，断电或中途失败不会损坏 data.json。
- 设置环境变量 NAV_TOKEN 后，保存数据需要输入这个密码；查看不需要密码。

用法：
    python3 server.py                      # 默认 0.0.0.0:8080
    python3 server.py --port 9000 --bind 127.0.0.1
    NAV_TOKEN='你的密码' python3 server.py

目录结构（默认）：
    ./index.html  ./server.py  ./icons/...   静态文件目录（--web）
    ./data/data.json  ./data/backups/        数据目录（--data），不会被网页直接访问
"""
import argparse
import hashlib
import hmac
import json
import os
import posixpath
import shutil
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, urlsplit

MAX_BYTES = 5 * 1024 * 1024
KEEP_BACKUPS = 100
LOCK = threading.Lock()
# 静态目录中不对外提供的文件
HIDDEN = {"/server.py", "/nav-hub.service"}


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Python 3.7 才内置 ThreadingHTTPServer，这里自己定义以兼容 3.6。"""
    daemon_threads = True
    allow_reuse_address = True


def etag_of(data: bytes) -> str:
    return '"%s"' % hashlib.sha256(data).hexdigest()[:32]


class Handler(SimpleHTTPRequestHandler):
    data_dir = "data"
    web_dir = "."

    def translate_path(self, path):
        # Python 3.6 的 SimpleHTTPRequestHandler 不支持 directory 参数，
        # 这里把请求路径映射到 --web 目录，并过滤掉 .. 等越界路径
        path = urlsplit(path).path
        trailing = path.rstrip().endswith("/")
        words = [w for w in posixpath.normpath(unquote(path)).split("/") if w and w not in (".", "..")]
        result = os.path.join(self.web_dir, *words)
        if trailing:
            result += "/"
        return result

    @property
    def data_file(self):
        return os.path.join(self.data_dir, "data.json")

    def route(self):
        return unquote(urlsplit(self.path).path)

    def send_bytes(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def fail(self, code, msg):
        self.send_bytes(code, json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8"))

    # ---------- 读取 ----------
    def do_GET(self):
        path = self.route()
        if path == "/data.json":
            with LOCK:
                if not os.path.exists(self.data_file):
                    return self.fail(404, "no data yet")
                with open(self.data_file, "rb") as f:
                    body = f.read()
            return self.send_bytes(200, body, extra={"ETag": etag_of(body)})
        real = os.path.abspath(self.translate_path(self.path))
        if path in HIDDEN or path.endswith(".tmp") or real == self.data_dir or real.startswith(self.data_dir + os.sep):
            return self.fail(404, "not found")
        return super().do_GET()

    def do_HEAD(self):
        self.do_GET()

    # ---------- 保存 ----------
    def do_PUT(self):
        if self.route() != "/data.json":
            return self.fail(405, "method not allowed")

        token = os.environ.get("NAV_TOKEN", "")
        if token:
            given = unquote(self.headers.get("X-Nav-Token", ""))
            if not hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8")):
                return self.fail(401, "password required")

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self.fail(400, "empty body")
        if length > MAX_BYTES:
            return self.fail(413, "too large")
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode("utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
                raise ValueError("missing groups")
        except Exception as e:  # noqa: BLE001
            return self.fail(400, "invalid data: %s" % e)

        os.makedirs(self.data_dir, exist_ok=True)
        backup_dir = os.path.join(self.data_dir, "backups")
        with LOCK:
            if os.path.exists(self.data_file):
                with open(self.data_file, "rb") as f:
                    old = f.read()
                if_match = self.headers.get("If-Match")
                if if_match and if_match != etag_of(old):
                    return self.fail(412, "modified elsewhere")
                if old != body:
                    os.makedirs(backup_dir, exist_ok=True)
                    stamp = time.strftime("%Y%m%d-%H%M%S") + "-%03d" % (int(time.time() * 1000) % 1000)
                    shutil.copy2(self.data_file, os.path.join(backup_dir, "data-%s.json" % stamp))
                    backups = sorted(n for n in os.listdir(backup_dir) if n.startswith("data-"))
                    for name in backups[:-KEEP_BACKUPS]:
                        os.remove(os.path.join(backup_dir, name))
            tmp = self.data_file + ".tmp"
            with open(tmp, "wb") as f:
                f.write(body)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.data_file)

        self.send_bytes(200, b'{"ok":true}', extra={"ETag": etag_of(body)})

    def log_message(self, fmt, *args):
        if self.command == "PUT":
            super().log_message(fmt, *args)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="导航站服务")
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--web", default=here, help="静态文件目录（放 index.html 的目录）")
    ap.add_argument("--data", default=os.path.join(here, "data"), help="数据与备份目录")
    args = ap.parse_args()

    Handler.data_dir = os.path.abspath(args.data)
    Handler.web_dir = os.path.abspath(args.web)
    os.makedirs(Handler.data_dir, exist_ok=True)

    srv = ThreadingHTTPServer((args.bind, args.port), Handler)
    print("导航站已启动: http://%s:%d  数据目录: %s  保存密码: %s"
          % (args.bind, args.port, Handler.data_dir, "已设置" if os.environ.get("NAV_TOKEN") else "未设置"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

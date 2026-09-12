"""Minimal OpenClaw-compatible CDP relay server.

Speaks just enough of the protocol the OpenClaw Chrome extension implements so we can
forward CDP commands to an already-logged-in tab. Nothing is injected into the page by
us; we only use Runtime.evaluate through the extension's own chrome.debugger session.

Protocol (from the extension's background.js):
  * preflight:            HEAD /            -> any 2xx
  * websocket:            GET /extension?token=<relayToken>
  * server -> extension:  {"type":"event","event":"connect.challenge","payload":{"nonce":...}}
  * extension -> server:  {"type":"req","id":...,"method":"connect","params":{...}}
  * server -> extension:  {"type":"res","id":...,"ok":true}
  * extension -> server:  {"method":"forwardCDPEvent","params":{method,params,...}}
  * server -> extension:  {"id":N,"method":"forwardCDPCommand","params":{method,params,sessionId}}
  * extension -> server:  {"id":N,"result":...} | {"id":N,"error":"..."}

Local control API:
  GET  /health          -> {"extension":bool,"tabs":{...}}
  POST /cmd  {method, params, sessionId?}  -> the extension's raw response
"""

import os
import base64
import hashlib
import hmac
import json
import queue
import struct
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 18793
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "change-me")
NONCE = "zcode-relay-nonce"

STATE = {
    "sock": None,
    "tabs": {},
    "pending": {},
    "next_id": 1,
    "lock": threading.Lock(),
}


def relay_token(token: str, port: int) -> str:
    msg = f"openclaw-extension-relay-v1:{port}".encode()
    return hmac.new(token.encode(), msg, hashlib.sha256).hexdigest()


def ws_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    header = bytearray([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    return bytes(header) + payload


def ws_send(sock, obj) -> None:
    sock.sendall(ws_frame(json.dumps(obj, ensure_ascii=False).encode()))


def ws_read(sock, buf: bytearray):
    """Read one frame. Returns (opcode, payload_bytes) or None on EOF."""
    def need(n):
        while len(buf) < n:
            chunk = sock.recv(65536)
            if not chunk:
                raise ConnectionError("eof")
            buf.extend(chunk)

    need(2)
    b1, b2 = buf[0], buf[1]
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    length = b2 & 0x7F
    off = 2
    if length == 126:
        need(4)
        length = struct.unpack_from(">H", buf, 2)[0]
        off = 4
    elif length == 127:
        need(10)
        length = struct.unpack_from(">Q", buf, 2)[0]
        off = 10
    if masked:
        need(off + 4)
        mask = bytes(buf[off:off + 4])
        off += 4
    else:
        mask = None
    need(off + length)
    payload = bytes(buf[off:off + length])
    del buf[:off + length]
    if mask:
        payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
    return opcode, payload


def ws_loop(sock):
    buf = bytearray()
    try:
        while True:
            opcode, payload = ws_read(sock, buf)
            if opcode == 0x8:
                break
            if opcode == 0x9:  # ping -> pong
                sock.sendall(ws_frame(payload, opcode=0xA))
                continue
            if opcode not in (0x1, 0x2):
                continue
            try:
                msg = json.loads(payload.decode("utf-8", "ignore"))
            except Exception:
                continue

            if msg.get("type") == "req" and msg.get("method") == "connect":
                ws_send(sock, {"type": "res", "id": msg.get("id"), "ok": True, "payload": {}})
                print("[relay] handshake ok", flush=True)
                continue

            mid = msg.get("id")
            if isinstance(mid, int):
                with STATE["lock"]:
                    q = STATE["pending"].pop(mid, None)
                if q:
                    q.put(msg)
                continue

            if msg.get("method") == "forwardCDPEvent":
                p = msg.get("params") or {}
                inner = p.get("params") or {}
                if p.get("method") == "Target.attachedToTarget":
                    sid = inner.get("sessionId")
                    ti = inner.get("targetInfo") or {}
                    if sid:
                        with STATE["lock"]:
                            STATE["tabs"][sid] = {
                                "targetId": ti.get("targetId"),
                                "url": ti.get("url"),
                                "title": ti.get("title"),
                            }
                        print(f"[relay] attached {sid} {ti.get('url')}", flush=True)
                elif p.get("method") == "Target.detachedFromTarget":
                    sid = inner.get("sessionId")
                    with STATE["lock"]:
                        STATE["tabs"].pop(sid, None)
                    print(f"[relay] detached {sid}", flush=True)
    except Exception as e:
        print("[relay] ws loop ended:", e, flush=True)
    finally:
        with STATE["lock"]:
            if STATE["sock"] is sock:
                STATE["sock"] = None
        try:
            sock.close()
        except Exception:
            pass


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OpenClawRelay/1.0"

    def log_message(self, fmt, *args):
        print("[relay] http " + (fmt % args), flush=True)

    # ---- helpers
    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- HTTP
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if self.headers.get("Upgrade", "").lower() == "websocket" and parsed.path == "/extension":
            qs = urllib.parse.parse_qs(parsed.query)
            got = (qs.get("token") or [""])[0]
            if got != relay_token(GATEWAY_TOKEN, PORT):
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
                print("[relay] rejected: bad token", flush=True)
                return
            key = self.headers.get("Sec-WebSocket-Key", "")
            accept = base64.b64encode(
                hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            ).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()

            sock = self.connection
            with STATE["lock"]:
                STATE["sock"] = sock
                STATE["tabs"].clear()
            print("[relay] extension connected", flush=True)
            ws_send(sock, {
                "type": "event",
                "event": "connect.challenge",
                "payload": {"nonce": NONCE},
            })
            ws_loop(sock)
            self.close_connection = True
            return

        if parsed.path == "/health":
            with STATE["lock"]:
                self._send_json(200, {
                    "extension": STATE["sock"] is not None,
                    "tabs": STATE["tabs"],
                })
            return

        if parsed.path == "/json/version":
            self._send_json(200, {"Browser": "openclaw-relay", "Protocol-Version": "1.3"})
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/cmd":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send_json(400, {"error": f"bad json: {e}"})
            return

        sock = STATE["sock"]
        if sock is None:
            self._send_json(503, {"error": "extension not connected"})
            return

        with STATE["lock"]:
            mid = STATE["next_id"]
            STATE["next_id"] += 1
            q = queue.Queue()
            STATE["pending"][mid] = q

        try:
            ws_send(sock, {"id": mid, "method": "forwardCDPCommand", "params": body})
        except Exception as e:
            with STATE["lock"]:
                STATE["pending"].pop(mid, None)
            self._send_json(502, {"error": f"send failed: {e}"})
            return

        try:
            resp = q.get(timeout=90)
        except queue.Empty:
            with STATE["lock"]:
                STATE["pending"].pop(mid, None)
            self._send_json(504, {"error": "timeout"})
            return

        self._send_json(200, resp)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    srv = Server(("127.0.0.1", PORT), Handler)
    print(f"[relay] listening on 127.0.0.1:{PORT}", flush=True)
    print(f"[relay] expected token: {relay_token(GATEWAY_TOKEN, PORT)}", flush=True)
    srv.serve_forever()

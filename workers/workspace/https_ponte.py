"""HTTPS na porta 8443: o site da Vercel (https) fala com o PC sem mixed content.

Nao usa Tailscale Serve (na VM o Serve esta preso no runneradmin).
Certificado: `tailscale cert` (Let's Encrypt da cauda).
  /api/*  -> uvicorn :8710
  resto   -> agente :8765  (frame, input, health)
"""
from __future__ import annotations

import http.client
import os
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("ARKHER_TS_HOST", "arkher-windows-24.tail91d201.ts.net")
PORT = int(os.environ.get("ARKHER_HTTPS_PORT", "8443"))
AGENT = ("127.0.0.1", int(os.environ.get("ARKHER_AGENT_PORT", "8765")))
API = ("127.0.0.1", int(os.environ.get("ARKHER_PORT", "8710")))
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "host"}


def cert_paths() -> tuple[Path, Path]:
    d = Path(os.environ.get("ARKHER_STATE", str(Path.home() / "arkher_state")))
    crt = Path(os.environ.get("ARKHER_TLS_CRT", str(d / f"{HOST}.crt")))
    key = Path(os.environ.get("ARKHER_TLS_KEY", str(d / f"{HOST}.key")))
    return crt, key


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[arkher-https] " + (fmt % args) + "\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Expose-Headers", "X-Arkher-W,X-Arkher-H,X-Arkher-Real-W,X-Arkher-Real-H,X-Arkher-Title")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def do_PATCH(self) -> None:
        self._proxy()

    def do_DELETE(self) -> None:
        self._proxy()

    def _proxy(self) -> None:
        path = self.path or "/"
        dest = API if path.startswith("/api") else AGENT
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n > 0 else None
        hdrs: dict[str, str] = {}
        for k, v in self.headers.items():
            if k.lower() in HOP:
                continue
            hdrs[k] = v
        try:
            conn = http.client.HTTPConnection(dest[0], dest[1], timeout=60)
            conn.request(self.command, path, body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in HOP or k.lower().startswith("access-control-"):
                    continue
                if k.lower() == "content-length":
                    continue
                self.send_header(k, v)
            self._cors()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)
            conn.close()
        except Exception as e:
            msg = ('{"ok":false,"code":"PONTE","message":%s}' % repr(str(e)[:200])).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self._cors()
            self.end_headers()
            self.wfile.write(msg)


def main() -> int:
    crt, key = cert_paths()
    if not crt.is_file() or not key.is_file():
        print(f"sem certificado Tailscale: {crt} / {key}", file=sys.stderr)
        print("rode: tailscale cert --cert-file ... --key-file ... " + HOST, file=sys.stderr)
        return 2
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(crt), str(key))
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    httpd.daemon_threads = True
    print(f"ARKHER HTTPS :{PORT} -> api :{API[1]} agente :{AGENT[1]} cert={crt.name}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

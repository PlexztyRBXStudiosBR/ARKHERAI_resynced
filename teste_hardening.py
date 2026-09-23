#!/usr/bin/env python3
"""Integração curta do modo seguro, limites, cancelamento e restart."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = "hardening-test-token-0123456789"
ORIGIN = "https://example.test"


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def request(base, path, method="GET", body=None, token=TOKEN, origin=ORIGIN):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json", "Origin": origin}
    if data is not None: headers["Content-Type"] = "application/json"
    if token: headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status, dict(r.headers), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode())
        except Exception: body = {}
        return e.code, dict(e.headers), body


def wait_up(base, proc):
    for _ in range(100):
        if proc.poll() is not None:
            raise AssertionError("agent saiu: " + (proc.stdout.read() if proc.stdout else ""))
        try:
            code, _, _ = request(base, "/health", token="")
            if code == 200: return
        except Exception:
            pass
        time.sleep(.05)
    raise AssertionError("agent não subiu")


def start(state, port):
    env = dict(os.environ)
    env.update({"ARKHER_PORT": str(port), "ARKHER_STATE": state,
                "ARKHER_AGENT_TOKEN": TOKEN, "ARKHER_CORS_ORIGINS": ORIGIN,
                "ARKHER_MAX_REQUEST_BYTES": "16384"})
    return subprocess.Popen([sys.executable, "agent.py"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    with tempfile.TemporaryDirectory(prefix="arkher-hardening-") as state:
        port = free_port(); base = "http://127.0.0.1:%d" % port
        proc = start(state, port)
        try:
            wait_up(base, proc)
            code, headers, health = request(base, "/health", token="")
            assert code == 200 and health["ready"] is True
            assert headers.get("Access-Control-Allow-Origin") == ORIGIN
            assert request(base, "/ls", token="")[0] == 401
            assert request(base, "/ready", token=TOKEN)[0] == 200
            metrics = request(base, "/metrics")[2]
            assert metrics["ok"] and "requests" in metrics["metrics"]
            assert request(base, "/write", "POST", {"path": "../escape.txt", "content": "x"})[0] == 400
            assert request(base, "/write", "POST", {"path": "ok.txt", "content": "ok"})[2]["bytes"] == 2
            command = sys.executable + " -c \"print('x'*5000000)\""
            code, _, result = request(base, "/exec", "POST", {"cmd": command, "timeout": 30})
            assert code == 200 and result["code"] == 0 and result["outputTruncated"]
            queued = request(base, "/station/job", "POST", {"job": {"id": "cancel-me", "kind": "command"}})[2]
            assert queued["ok"]
            cancelled = request(base, "/station/job/cancel", "POST", {"jobId": "cancel-me", "reason": "teste"})[2]
            assert cancelled["ok"] and cancelled["job"]["status"] == "cancelled"
            spawned = request(base, "/spawn", "POST", {"cmd": sys.executable + " -c \"import time; time.sleep(30)\""})[2]
            assert spawned["ok"]
        finally:
            proc.terminate(); proc.wait(timeout=8)
        proc = start(state, port)
        try:
            wait_up(base, proc)
            jobs = request(base, "/jobs")[2]
            recovered = next(x for x in jobs["items"] if x["id"] == spawned["id"])
            assert recovered["done"] and recovered["status"] == "aborted"
        finally:
            proc.terminate(); proc.wait(timeout=8)
    print("✅ HARDENING OK — auth, CORS, limites, path sandbox, cancelamento e restart passaram")


if __name__ == "__main__":
    main()

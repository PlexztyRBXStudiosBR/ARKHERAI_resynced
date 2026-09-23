#!/usr/bin/env python3
"""Carga/falha local do endpoint HTTP, sem dependências externas.

Por padrão sobe um agente efêmero, dispara requests concorrentes e verifica que
falhas de autenticação/traversal são rejeitadas. Não mede qualidade de engines;
mede apenas comportamento do serviço sob concorrência.
"""
import argparse
import concurrent.futures
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
TOKEN = "load-test-token-0123456789012345"


def port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def call(base, route, token=TOKEN):
    started = time.perf_counter()
    headers = {"Accept": "application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + route, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            res.read(256 * 1024)
            code = res.status
    except urllib.error.HTTPError as exc:
        code = exc.code
        try: exc.read(64 * 1024)
        except Exception: pass
    except Exception:
        code = 599
    return code, (time.perf_counter() - started) * 1000


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=120)
    ap.add_argument("--concurrency", type=int, default=32)
    args = ap.parse_args(argv)
    n = max(1, min(2000, args.requests)); workers = max(1, min(128, args.concurrency))
    with tempfile.TemporaryDirectory(prefix="arkher-load-") as state:
        p = port(); base = "http://127.0.0.1:%d" % p
        env = dict(os.environ, ARKHER_PORT=str(p), ARKHER_STATE=state,
                   ARKHER_AGENT_TOKEN=TOKEN, ARKHER_CORS_ORIGINS="https://load.test")
        proc = subprocess.Popen([sys.executable, "agent.py"], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    if call(base, "/health", token="")[0] == 200: break
                except Exception: pass
                time.sleep(.05)
            else: raise AssertionError("agent não subiu")
            routes = ["/health" if i % 2 == 0 else "/ls" for i in range(n)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(lambda route: call(base, route), routes))
            bad = [x for x in results if x[0] != 200]
            lat = sorted(x[1] for x in results)
            p95 = lat[min(len(lat) - 1, int(len(lat) * .95))]
            assert not bad, "requests válidos falharam: %s" % bad[:5]
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                denied = list(pool.map(lambda _: call(base, "/ls", token="wrong-token"), range(max(10, workers))))
            assert all(code == 401 for code, _ in denied), denied[:5]
            print("✅ CARGA OK — %d requests, concorrência %d, p95 %.1f ms, auth inválida rejeitada" %
                  (n, workers, p95))
        finally:
            proc.terminate()
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()


if __name__ == "__main__":
    main()

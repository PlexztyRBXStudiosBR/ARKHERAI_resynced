#!/usr/bin/env python3
"""Smoke test do preflight sem rede, engines ou dependências externas."""
import argparse
import os
import tempfile
from pathlib import Path

import arkher_doctor


ROOT = Path(__file__).resolve().parent


def args(state, **kwargs):
    base = dict(root=str(ROOT), state=str(state), agent="", token="",
                allow_insecure=True, min_free_gb=0.001, engines=None,
                require_engines=False, strict=False)
    base.update(kwargs)
    return argparse.Namespace(**base)


def main():
    with tempfile.TemporaryDirectory(prefix="arkher-doctor-test-") as state:
        report = arkher_doctor.run(args(state))
        failures = [x for x in report["checks"] if x["status"] == "fail"]
        assert report["ok"], failures
        assert any(x["name"] == "state:writable" and x["status"] == "ok"
                   for x in report["checks"])
        strict = arkher_doctor.run(args(state, allow_insecure=False))
        assert not strict["ok"]
        assert any(x["name"] == "auth:token" and x["status"] == "fail"
                   for x in strict["checks"])
    print("✅ DOCTOR OK — preflight seguro e modo legado explícito passaram")


if __name__ == "__main__":
    main()

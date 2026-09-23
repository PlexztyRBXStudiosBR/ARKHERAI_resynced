import os
import sys
import tempfile
from pathlib import Path

# Backend testa contra diretório de dados isolado e SEM checkpoint (estado honesto).
_TMP = tempfile.mkdtemp(prefix="arkher-test-")
os.environ["ARKHER_DATA_DIR"] = _TMP
os.environ["ARKHER_CHECKPOINT"] = str(Path(_TMP) / "checkpoint-inexistente.pt")
os.environ["ARKHER_TOKENIZER"] = str(Path(_TMP) / "vocab-inexistente.json")
os.environ["ARKHER_RATE_CHAT_PER_MIN"] = "1000"
os.environ["ARKHER_RATE_API_PER_MIN"] = "5000"

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.model import runtime as model_runtime  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    res = client.post("/api/auth/device", json={"name": "teste"})
    token = res.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture()
def auth_client_b(client):
    res = client.post("/api/auth/device", json={"name": "outra-pessoa"})
    token = res.json()["token"]
    fresh = TestClient(app)
    fresh.headers.update({"Authorization": f"Bearer {token}"})
    return fresh


class FakeInfo:
    checkpoint_version = "fake-v0"
    checkpoint_path = "fake"
    device = "cpu"
    num_parameters = 1000
    context_window = 128
    vocab_size = 100
    quality = "teste"


class FakeEngine:
    """Motor falso apenas para testes de fluxo — nunca usado em produção."""

    def __init__(self, resposta="Resposta de teste da ARKHER."):
        self.info = FakeInfo()
        self.resposta = resposta

    def encode(self, text):
        return list(range(10))

    def decode(self, ids):
        if not ids:
            return ""
        return self.resposta[: len(ids)]

    def generate(self, prompt_ids, max_new_tokens, temperature=0.8, stop_event=None, deadline=None):
        for i in range(len(self.resposta)):
            if stop_event is not None and stop_event.is_set():
                return
            yield i


@pytest.fixture()
def fake_model():
    old_state = model_runtime._STATE
    old_engine = model_runtime._ENGINE
    model_runtime._ENGINE = FakeEngine()
    model_runtime._STATE = "ready"
    yield model_runtime
    model_runtime._STATE = old_state
    model_runtime._ENGINE = old_engine


def read_sse(text: str) -> list[tuple[str, dict]]:
    import json

    events = []
    for block in text.split("\n\n"):
        ev, data = "message", None
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if data is not None:
            events.append((ev, data))
    return events

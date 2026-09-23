"""Motor de inferência do ARKHER-1.

Carrega o tokenizer e o checkpoint locais versionados e gera tokens com:
- temperatura/amostragem simples;
- parada por <eos>;
- verificação cooperativa de cancelamento a cada token;
- nenhum acesso à rede.
"""
from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from model.architecture.transformer import Arkher1, ArkherConfig  # noqa: E402
from model.tokenizer.bpe import BpeTokenizer  # noqa: E402


@dataclass
class EngineInfo:
    checkpoint_version: str
    checkpoint_path: str
    device: str
    num_parameters: int
    context_window: int
    vocab_size: int
    quality: str


class InferenceEngine:
    def __init__(self, tokenizer_path: Path, checkpoint_path: Path):
        self.tokenizer = BpeTokenizer.load(Path(tokenizer_path))
        payload = torch.load(Path(checkpoint_path), map_location="cpu", weights_only=False)
        cfg = ArkherConfig.from_dict(payload["config"])
        self.device = torch.device("cpu")
        self.model = Arkher1(cfg)
        self.model.load_state_dict(payload["state_dict"])
        self.model.to(self.device)
        self.model.eval()
        for t in (torch.get_num_threads(),):
            torch.set_num_threads(max(1, t))
        self.info = EngineInfo(
            checkpoint_version=str(payload.get("version", "desconhecida")),
            checkpoint_path=str(checkpoint_path),
            device=str(self.device),
            num_parameters=self.model.num_parameters(),
            context_window=cfg.context_window,
            vocab_size=cfg.vocab_size,
            quality=str(payload.get("quality", "experimental")),
        )

    # ------------------------------------------------------------------ api
    def encode(self, text: str) -> list[int]:
        return self.tokenizer.encode(text, add_bos=True)

    def decode(self, ids: list[int]) -> str:
        return self.tokenizer.decode(ids)

    @torch.no_grad()
    def generate(
        self,
        prompt_ids: list[int],
        max_new_tokens: int,
        temperature: float = 0.8,
        stop_event: threading.Event | None = None,
        deadline: float | None = None,
    ):
        """Gerador de ids de token. Interrompe por cancelamento, timeout ou <eos>."""
        ctx = self.info.context_window
        ids = prompt_ids[-ctx:]
        generated = 0
        while generated < max_new_tokens:
            if stop_event is not None and stop_event.is_set():
                return
            if deadline is not None and time.monotonic() > deadline:
                return
            x = torch.tensor([ids[-ctx:]], dtype=torch.long)
            logits = self.model.next_logits(x)
            if temperature <= 0.0:
                nxt = int(logits.argmax(dim=-1).item())
            else:
                probs = torch.softmax(logits / max(1e-3, temperature), dim=-1)
                nxt = int(torch.multinomial(probs, num_samples=1).item())
            if nxt == self.tokenizer.eos_id:
                return
            ids.append(nxt)
            generated += 1
            yield nxt

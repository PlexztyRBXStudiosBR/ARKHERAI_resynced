#!/usr/bin/env python3
"""Treino do ARKHER-1 em CPU, com checkpoint versionado, retomada e log de perda.

Uso:
  python -m model.training.train                 # treino novo
  python -m model.training.train --resume X.pt   # retomar de checkpoint
  python -m model.training.train --epochs 4
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import torch

from model.architecture.transformer import Arkher1, ArkherConfig
from model.tokenizer.bpe import BpeTokenizer
from model.training.common import (
    CHECKPOINT_DIR,
    PREPARED_PATH,
    VOCAB_PATH,
    dataset_hash,
    git_commit,
    load_model_yaml,
    log,
    write_state,
)


def build_sequences(ids: list[int], ctx: int) -> torch.Tensor:
    n = (len(ids) - 1) // ctx
    if n < 8:
        raise SystemExit("corpus pequeno demais para treinar")
    xs = torch.tensor(ids[: n * ctx], dtype=torch.long).view(n, ctx)
    ys = torch.tensor(ids[1 : n * ctx + 1], dtype=torch.long).view(n, ctx)
    return torch.stack([xs, ys], dim=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--resume", type=str, default=None)
    ap.add_argument("--teacher", type=str, default=None, help="checkpoint do modelo anterior (destila o novo)")
    ap.add_argument("--gen", type=int, default=0, help="geração da linhagem; 0 = config.yaml")
    ap.add_argument("--tag", type=str, default="demo")
    args = ap.parse_args()

    y = load_model_yaml()
    m = y["model"]
    tcfg = y["training"]
    torch.manual_seed(int(tcfg["seed"]))
    torch.set_num_threads(max(1, torch.get_num_threads()))

    tok = BpeTokenizer.load(VOCAB_PATH)
    text = PREPARED_PATH.read_text(encoding="utf-8")
    ids = tok.encode(text)
    log(f"corpus: {len(ids):,} tokens")

    ctx = int(m["context_window"])
    data = build_sequences(ids, ctx)
    n_val = max(4, len(data) // 10)
    perm = torch.randperm(len(data))
    val_idx = perm[:n_val]
    train_idx = perm[n_val:]
    log(f"sequências: treino={len(train_idx)} validação={len(val_idx)}")

    from model.training import linhagem as _lin

    teacher = None
    teacher_ctx = ctx
    gen_meta = args.gen or 2
    if args.gen:
        rung = _lin.rung_por_gen(args.gen)
        ctx = int(rung["context_window"])
        data = build_sequences(ids, ctx)
        n_val = max(4, len(data) // 10)
        perm = torch.randperm(len(data))
        val_idx = perm[:n_val]
        train_idx = perm[n_val:]
        cfg = ArkherConfig(
            vocab_size=min(len(tok.vocab), int(rung["vocab_size"])),
            context_window=ctx,
            n_layers=int(rung["n_layers"]),
            n_heads=int(rung["n_heads"]),
            d_model=int(rung["d_model"]),
            d_ff=int(rung["d_ff"]),
            dropout=float(m["dropout"]),
            tie_embeddings=bool(m["tie_embeddings"]),
        )
        model = Arkher1(cfg)
        start_epoch = 0
        global_step = 0
        gen_meta = int(rung["gen"])
        log(f"geração {gen_meta} {rung['nome']} (alvo ~{rung['params_alvo']:,})")
        if args.teacher or args.resume:
            tpath = args.teacher or args.resume
            tpay = torch.load(tpath, map_location="cpu", weights_only=False)
            tcfg = ArkherConfig.from_dict(tpay["config"])
            teacher = Arkher1(tcfg)
            teacher.load_state_dict(tpay["state_dict"])
            teacher.eval()
            for p in teacher.parameters():
                p.requires_grad_(False)
            teacher_ctx = tcfg.context_window
            st = model.state_dict()
            ncopy = _lin.copiar_state_compativel(tpay["state_dict"], st)
            model.load_state_dict(st)
            log(f"professor {tpath}: {ncopy} tensores copiados; resto nasce nesta geração")
            args.resume = None
    elif args.resume:
        payload = torch.load(args.resume, map_location="cpu", weights_only=False)
        cfg = ArkherConfig.from_dict(payload["config"])
        model = Arkher1(cfg)
        model.load_state_dict(payload["state_dict"])
        start_epoch = int(payload.get("meta", {}).get("epoch", 0))
        global_step = int(payload.get("meta", {}).get("steps", 0))
        log(f"retomando de {args.resume} (época {start_epoch})")
    else:
        cfg = ArkherConfig(
            vocab_size=len(tok.vocab),
            context_window=ctx,
            n_layers=int(m["n_layers"]),
            n_heads=int(m["n_heads"]),
            d_model=int(m["d_model"]),
            d_ff=int(m["d_ff"]),
            dropout=float(m["dropout"]),
            tie_embeddings=bool(m["tie_embeddings"]),
        )
        model = Arkher1(cfg)
        start_epoch = 0
        global_step = 0
    log(f"parâmetros: {model.num_parameters():,}")

    opt = torch.optim.AdamW(
        model.parameters(), lr=float(tcfg["learning_rate"]), weight_decay=float(tcfg["weight_decay"])
    )
    bs = int(tcfg["batch_size"])
    warmup = int(tcfg["warmup_steps"])
    base_lr = float(tcfg["learning_rate"])
    history: list[float] = []

    write_state({
        "status": "rodando",
        "checkpoint_base": args.resume or "novo",
        "parametros": model.num_parameters(),
        "tokens": len(ids),
        "epochs_alvo": args.epochs,
        "perda": [],
        "inicio": time.time(),
    })

    for epoch in range(start_epoch, args.epochs):
        ordem = train_idx[torch.randperm(len(train_idx))]
        total = 0.0
        nb = 0
        t0 = time.time()
        for b in range(0, len(ordem), bs):
            batch = data[ordem[b : b + bs]]
            x, tgt = batch[:, 0, :], batch[:, 1, :]
            global_step += 1
            lr = base_lr * min(1.0, global_step / max(1, warmup))
            for g in opt.param_groups:
                g["lr"] = lr
            logits, loss = model(x, tgt)
            if teacher is not None:
                tlen = min(x.size(1), teacher_ctx)
                with torch.no_grad():
                    t_logits, _ = teacher(x[:, :tlen])
                # destila só o vocabulário comum
                v = min(logits.size(-1), t_logits.size(-1))
                s = torch.nn.functional.log_softmax(logits[:, :tlen, :v] / 2.0, dim=-1)
                tt = torch.nn.functional.softmax(t_logits[:, :, :v] / 2.0, dim=-1)
                kl = torch.nn.functional.kl_div(s, tt, reduction="batchmean") * 4.0
                loss = 0.6 * loss + 0.4 * kl
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(tcfg["gradient_clip"]))
            opt.step()
            total += float(loss.item())
            nb += 1
            if nb % 5 == 0:
                history.append(round(total / nb, 4))
                write_state({
                    "status": "rodando",
                    "epoch": epoch + 1,
                    "epochs_alvo": args.epochs,
                    "passo": global_step,
                    "perda_media": round(total / nb, 4),
                    "perda": history[-200:],
                    "segundos": round(time.time() - t0, 1),
                })
        val = 0.0
        nv = 0
        with torch.no_grad():
            for b in range(0, len(val_idx), bs):
                batch = data[val_idx[b : b + bs]]
                _, loss = model(batch[:, 0, :], batch[:, 1, :])
                val += float(loss.item())
                nv += 1
        val_loss = val / max(1, nv)
        log(f"época {epoch + 1}/{args.epochs} perda_treino={total / nb:.4f} perda_val={val_loss:.4f} ({time.time() - t0:.0f}s)")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    version = f"arkher1-g{gen_meta}-v{m['version']}-{args.tag}"
    out = CHECKPOINT_DIR / f"{version}.pt"
    torch.save(
        {
            "version": version,
            "quality": "experimental",
            "config": cfg.__dict__,
            "state_dict": model.state_dict(),
            "meta": {
                "git": git_commit(),
                "dataset": dataset_hash(),
                "epoch": args.epochs,
                "steps": global_step,
                "final_train_loss": round(total / max(1, nb), 4),
                "final_val_loss": round(val_loss, 4),
                "tokens": len(ids),
                "gen": gen_meta,
                "teacher": args.teacher,
            },
        },
        out,
    )
    latest = CHECKPOINT_DIR / "latest.pt"
    latest.write_bytes(out.read_bytes())
    write_state({
        "status": "concluido",
        "checkpoint": str(out),
        "versao": version,
        "perda_final_treino": round(total / max(1, nb), 4),
        "perda_final_validacao": round(val_loss, 4),
        "perplexidade_validacao": round(math.exp(min(20.0, val_loss)), 2),
        "passos": global_step,
        "perda": history[-200:],
    })
    log(f"checkpoint salvo: {out}")
    try:
        from model.training import linhagem as _lin2

        _lin2.registrar(gen_meta, args.teacher, 0, 0)
    except Exception as e:  # noqa: BLE001
        log(f"aviso: linhagem não registrada ({e})")


if __name__ == "__main__":
    main()

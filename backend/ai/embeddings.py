"""SPECTER2 on CPU. The model is loaded on the first embed call, never onto a GPU."""

from __future__ import annotations

import threading
from pathlib import Path

_lock = threading.Lock()
_tokenizer = None
_model = None


def specter_input(title: str, abstract: str, sep: str = "[SEP]") -> str:
    title = (title or "").strip()
    abstract = (abstract or "").strip()
    if abstract:
        return f"{title}{sep}{abstract}"
    return title


def _load():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model
    # The default 10s Hugging Face read timeout drops the SPECTER2 weights
    # on a slow link and leaves the job sitting on Embed.
    import os

    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    try:
        import torch
        from adapters import AutoAdapterModel
        from huggingface_hub.file_download import _are_symlinks_supported_in_dir
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "SPECTER2 is not installed. From backend/: "
            "pip install torch --index-url https://download.pytorch.org/whl/cpu "
            "&& pip install -r requirements-embed.txt"
        ) from exc

    torch.set_num_threads(min(4, torch.get_num_threads()))
    # Windows without Developer Mode cannot create the cache symlinks Hugging Face
    # expects, and a parallel download then crashes. Force plain file copies.
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    for name in ("models--allenai--specter2_base", "models--allenai--specter2"):
        _are_symlinks_supported_in_dir[str((hub / name).resolve())] = False
    tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    # allenai/specter2 is the citation-proximity adapter.
    model.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=True)
    model = model.to("cpu")
    model.eval()
    _tokenizer = tokenizer
    _model = model
    return tokenizer, model


def embed_paper(title: str, abstract: str) -> list[float]:
    import torch

    with _lock:
        tokenizer, model = _load()
        text = specter_input(title, abstract, sep=tokenizer.sep_token or "[SEP]")
        inputs = tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            output = model(**inputs)
            vector = output.last_hidden_state[0, 0, :].detach().cpu().tolist()
    if len(vector) != 768:
        raise RuntimeError(f"SPECTER2 returned {len(vector)} dimensions, expected 768")
    return [float(value) for value in vector]

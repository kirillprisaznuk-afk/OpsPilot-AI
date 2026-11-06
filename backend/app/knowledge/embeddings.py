"""Pinned MiniLM ONNX inference; downloads are an explicit maintenance operation."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from app.core.config import settings
from tokenizers import Tokenizer

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIMENSION = 384
FILES = ["onnx/model.onnx", "tokenizer.json", "config.json", "README.md"]
FILE_HASHES = {
    "onnx/model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    "config.json": "953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41",
}
CONFIG = {
    "model": MODEL,
    "revision": REVISION,
    "dimension": DIMENSION,
    "pooling": "attention_mask_mean",
    "normalization": "L2",
    "distance": "cosine",
    "max_tokens": 256,
    "backend": "onnx-cpu-float32",
    "parser": "markdown-sections-v1",
    "tokenizer_truncation": "reject_over_256",
}
CONFIG_ID = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()


class KnowledgeError(Exception):
    def __init__(self, code, message, status=503):
        super().__init__(message)
        self.code, self.status = code, status


def download_model():
    from huggingface_hub import hf_hub_download

    root = Path(settings().embedding_cache)
    root.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        hf_hub_download(MODEL, name, revision=REVISION, local_dir=root)
    verify_model_files(root)
    (root / "revision.json").write_text(json.dumps(CONFIG, sort_keys=True))
    return {"model": MODEL, "revision": REVISION, "cache_initialized": True}


def verify_model_files(root):
    for name, expected in FILE_HASHES.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise KnowledgeError(
                "model_integrity_failure", "Pinned model file checksum validation failed."
            )


class LocalEmbeddings:
    def __init__(self):
        root = Path(settings().embedding_cache)
        if not all((root / name).is_file() for name in FILES + ["revision.json"]):
            raise KnowledgeError(
                "model_unavailable", "Run the explicit knowledge download-model command."
            )
        if json.loads((root / "revision.json").read_text()) != CONFIG:
            raise KnowledgeError(
                "model_mismatch", "Model cache configuration differs; initialize the pinned model."
            )
        verify_model_files(root)
        self.tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.runtime = ort.InferenceSession(
            str(root / "onnx/model.onnx"), options, providers=["CPUExecutionProvider"]
        )

    def token_count(self, value):
        return len(self.tokenizer.encode(value).ids)

    def encode(self, texts):
        result = []
        for start in range(0, len(texts), 16):
            batch = texts[start : start + 16]
            if any(self.token_count(t) > 256 for t in batch):
                raise KnowledgeError(
                    "text_too_long", "Embedding text exceeds the model token limit.", 422
                )
            encoded = self.tokenizer.encode_batch(batch)
            inputs = {
                "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in encoded], dtype=np.int64),
            }
            hidden = self.runtime.run(None, inputs)[0]
            mask = inputs["attention_mask"][..., None].astype(np.float32)
            vectors = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
            vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
            if vectors.shape != (len(batch), DIMENSION) or not np.isfinite(vectors).all():
                raise KnowledgeError("invalid_embedding", "Embedding output failed validation.")
            result.extend(vectors.tolist())
        return result


@lru_cache(maxsize=1)
def provider():
    return LocalEmbeddings()

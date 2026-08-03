"""Download fastembed ONNX weights into the image cache at Docker build time."""

from __future__ import annotations

import os
from pathlib import Path

from fastembed import TextEmbedding

from mcp_server.infrastructure.embeddings.fastembed_model_catalog import resolve_embedding_model


def main() -> None:
    model_name = os.environ.get(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    dimensions = int(os.environ.get("EMBEDDING_DIMENSION", "384"))
    cache_dir = os.environ.get("EMBEDDING_CACHE_DIR", "/app/model-cache/fastembed")

    resolved = resolve_embedding_model(model_name, dimensions)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    model = TextEmbedding(model_name=resolved.model_name, cache_dir=cache_dir)
    list(model.embed(["warmup"]))
    print(f"Warmed embedding model {resolved.model_name} -> {cache_dir}")


if __name__ == "__main__":
    main()

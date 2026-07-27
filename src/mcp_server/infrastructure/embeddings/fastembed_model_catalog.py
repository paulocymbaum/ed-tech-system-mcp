"""Resolve configured embedding model ids to fastembed-supported ONNX models."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

# fastembed 0.8 does not ship ONNX for e5-small; map to closest multilingual 384d model.
_UNSUPPORTED_MODEL_ALIASES: dict[str, str] = {
    "intfloat/multilingual-e5-small": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "intfloat/multilingual-e5-base": "intfloat/multilingual-e5-large",
}


@dataclass(frozen=True, slots=True)
class ResolvedEmbeddingModel:
    """Concrete fastembed model to load at runtime."""

    model_name: str
    dimensions: int
    use_e5_prefixes: bool
    requested_model: str


@lru_cache(maxsize=1)
def supported_fastembed_models() -> dict[str, int]:
    """Return supported fastembed model ids and their vector dimensions."""
    from fastembed import TextEmbedding

    return {entry["model"]: entry["dim"] for entry in TextEmbedding.list_supported_models()}


def resolve_embedding_model(model_name: str, dimensions: int) -> ResolvedEmbeddingModel:
    """Map configured model ids to a fastembed-supported model."""
    supported = supported_fastembed_models()
    if model_name in supported:
        return ResolvedEmbeddingModel(
            model_name=model_name,
            dimensions=supported[model_name],
            use_e5_prefixes="e5" in model_name.lower(),
            requested_model=model_name,
        )

    fallback = _UNSUPPORTED_MODEL_ALIASES.get(model_name)
    if fallback is not None and fallback in supported:
        return ResolvedEmbeddingModel(
            model_name=fallback,
            dimensions=supported[fallback],
            use_e5_prefixes="e5" in fallback.lower(),
            requested_model=model_name,
        )

    sample = ", ".join(sorted(supported)[:6])
    msg = (
        f"Embedding model '{model_name}' is not supported by fastembed. "
        f"Set EMBEDDING_MODEL to a supported id (e.g. {sample})."
    )
    if dimensions != supported.get(model_name, dimensions):
        _ = dimensions
    raise ValueError(msg)

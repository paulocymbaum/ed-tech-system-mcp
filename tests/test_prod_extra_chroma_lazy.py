"""Prod extra omits chromadb; wiring imports Chroma only for that backend."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from mcp_server.wiring import build_vector_index_writer, build_vector_retriever

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_prod_extra_is_workflow_plus_rag_without_chromadb() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = pyproject["project"]["optional-dependencies"]
    assert "chromadb" not in extras["prod"]
    assert "fastembed" in extras["prod"]
    assert "langgraph" in extras["prod"]
    assert any(dep.startswith("chromadb") for dep in extras["full"])
    assert any(dep.startswith("chromadb") for dep in extras["rag"])


def test_wiring_chroma_imports_are_inside_chroma_branch() -> None:
    tree = ast.parse((REPO_ROOT / "src/mcp_server/wiring.py").read_text(encoding="utf-8"))
    chroma_imports: list[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "chroma_vector" in node.module:
            chroma_imports.append(node)
    assert chroma_imports
    chroma_retriever = (
        REPO_ROOT / "src/mcp_server/infrastructure/retrieval/chroma_vector_retriever.py"
    ).read_text(encoding="utf-8")
    assert "import chromadb" in chroma_retriever


def test_supabase_backend_builds_without_chroma_modules() -> None:
    settings = SimpleNamespace(
        vector_store_backend="supabase",
        supabase_vector_enabled=True,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key=SecretStr("service-role"),
        chroma_persist_path=".cache/chromadb",
        chroma_collection_name="chunks",
    )
    retriever = build_vector_retriever(settings)
    writer = build_vector_index_writer(settings)
    assert retriever.__class__.__name__ == "SupabasePgvectorRetriever"
    assert writer.__class__.__name__ == "SupabaseVectorIndexWriter"

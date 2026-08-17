"""Curriculum constrained values shared with backend enums and PraxisWeb catalog types.

Sources of truth (lockstep-tested):
- ``ed-tech-system-backend/supabase/migrations/20260724120100_curriculum_foundation.sql``
- ``ed-tech-system-backend/supabase/migrations/20260816120000_lesson_stacks_test_boilerplates.sql``
- ``PraxisWeb/frontend/src/domain/types/catalog.ts`` (``ProjectEntry.kind``, ``Project.stack``)
- ``PraxisWeb/frontend/src/infrastructure/author-cms/authorCmsApi.ts`` (upsert payloads use ``file``)
"""

from __future__ import annotations

# curriculum.project_file_kind + PraxisWeb ProjectEntry.kind
PROJECT_FILE_KINDS = frozenset({"dir", "file"})

# Harness / LLM labels that must be remapped before upsert_project_tree
PROJECT_FILE_KIND_ALIASES: dict[str, str] = {
    "dir": "dir",
    "directory": "dir",
    "file": "file",
    "readme": "file",
    "starter": "file",
    "solution": "file",
    "test": "file",
    "tests": "file",
}

# curriculum.lesson_stack + PraxisWeb Project.stack
LESSON_STACKS = frozenset({"javascript", "typescript", "react", "cpp", "python"})

# curriculum.test_boilerplates.runner_kind CHECK
RUNNER_KINDS = frozenset({"browser-js", "node", "pytest", "cpp-cli", "react-test"})

# curriculum.lesson_run_dependencies.kind CHECK
RUN_DEPENDENCY_KINDS = frozenset({"npm", "pip", "cdn", "system", "header"})

# curriculum.mock_section_type
MOCK_SECTION_TYPES = frozenset({"instructions", "quiz", "coding"})

# curriculum.lesson_status (authoring upserts draft; publish RPC advances)
LESSON_STATUSES = frozenset({"draft", "published", "composite"})

# curriculum.module_kind
MODULE_KINDS = frozenset({"study", "mock"})

# curriculum.graph_node_kind (search_graph_nodes / FE coverage)
GRAPH_NODE_KINDS = frozenset({"root", "module", "section", "lesson"})


def normalize_project_file_kind(
    kind: object,
    *,
    path: str = "",
    content: object = None,
) -> str:
    """Map harness labels to ``curriculum.project_file_kind`` (``dir`` | ``file``)."""
    raw = str(kind or "").strip().lower()
    if raw in PROJECT_FILE_KIND_ALIASES:
        return PROJECT_FILE_KIND_ALIASES[raw]
    if content is None:
        leaf = str(path).rstrip("/").rsplit("/", 1)[-1]
        if leaf and "." not in leaf:
            return "dir"
    return "file"

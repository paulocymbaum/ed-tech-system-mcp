"""Lockstep: MCP curriculum enums match backend SQL + PraxisWeb catalog types."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mcp_server.domain.curriculum_enums import (
    GRAPH_NODE_KINDS,
    LESSON_STACKS,
    LESSON_STATUSES,
    MOCK_SECTION_TYPES,
    MODULE_KINDS,
    PROJECT_FILE_KINDS,
    RUN_DEPENDENCY_KINDS,
    RUNNER_KINDS,
    normalize_project_file_kind,
)
from mcp_server.domain.content_validators import (
    KNOWN_LESSON_STACKS,
    KNOWN_PROJECT_FILE_KINDS,
    KNOWN_RUN_DEPENDENCY_KINDS,
    KNOWN_RUNNER_KINDS,
    validate_lesson_stack,
    validate_project_files_for_rpc,
    validate_run_dependencies,
    validate_test_boilerplate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT.parent / "ed-tech-system-backend"
PRAXIS_ROOT = REPO_ROOT.parent / "PraxisWeb"

FOUNDATION_SQL = (
    BACKEND_ROOT / "supabase/migrations/20260724120100_curriculum_foundation.sql"
)
STACKS_SQL = (
    BACKEND_ROOT
    / "supabase/migrations/20260816120000_lesson_stacks_test_boilerplates.sql"
)
CATALOG_TS = PRAXIS_ROOT / "frontend/src/domain/types/catalog.ts"
AUTHOR_CMS_TS = PRAXIS_ROOT / "frontend/src/infrastructure/author-cms/authorCmsApi.ts"


def _require_sibling(path: Path) -> Path:
    if not path.is_file():
        pytest.skip(f"sibling source missing: {path}")
    return path


def _enum_values(sql: str, type_name: str) -> frozenset[str]:
    match = re.search(
        rf"CREATE TYPE\s+{re.escape(type_name)}\s+AS ENUM\s*\((.*?)\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"enum {type_name} not found"
    return frozenset(re.findall(r"'([^']+)'", match.group(1)))


def _check_in_list(sql: str, constraint_fragment: str) -> frozenset[str]:
    match = re.search(
        rf"{re.escape(constraint_fragment)}\s*\(([^)]+)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"CHECK list for {constraint_fragment!r} not found"
    return frozenset(re.findall(r"'([^']+)'", match.group(1)))


@pytest.mark.parametrize(
    ("type_name", "mcp_set"),
    [
        ("curriculum.project_file_kind", PROJECT_FILE_KINDS),
        ("curriculum.mock_section_type", MOCK_SECTION_TYPES),
        ("curriculum.lesson_status", LESSON_STATUSES),
        ("curriculum.module_kind", MODULE_KINDS),
        ("curriculum.graph_node_kind", GRAPH_NODE_KINDS),
    ],
)
def test_mcp_enums_match_backend_foundation(type_name: str, mcp_set: frozenset[str]) -> None:
    sql = _require_sibling(FOUNDATION_SQL).read_text(encoding="utf-8")
    assert mcp_set == _enum_values(sql, type_name)


def test_mcp_lesson_stack_and_checks_match_backend_e16() -> None:
    sql = _require_sibling(STACKS_SQL).read_text(encoding="utf-8")
    assert LESSON_STACKS == _enum_values(sql, "curriculum.lesson_stack")
    assert RUNNER_KINDS == _check_in_list(sql, "runner_kind IN")
    assert RUN_DEPENDENCY_KINDS == _check_in_list(sql, "CONSTRAINT lesson_run_dependencies_kind_known CHECK (\n    kind IN")


def test_mcp_project_file_kind_and_stack_match_praxisweb_catalog() -> None:
    text = _require_sibling(CATALOG_TS).read_text(encoding="utf-8")
    kind_match = re.search(
        r"export type ProjectEntry = \{[^}]*kind:\s*\"([^\"]+)\"\s*\|\s*\"([^\"]+)\"",
        text,
        flags=re.DOTALL,
    )
    assert kind_match, "ProjectEntry.kind union not found in catalog.ts"
    assert PROJECT_FILE_KINDS == frozenset(kind_match.groups())

    stack_match = re.search(
        r"stack\?:\s*((?:\"[^\"]+\"\s*\|\s*)+\"[^\"]+\")",
        text,
    )
    assert stack_match, "Project.stack union not found in catalog.ts"
    fe_stacks = frozenset(re.findall(r"\"([^\"]+)\"", stack_match.group(1)))
    assert LESSON_STACKS == fe_stacks


def test_praxisweb_author_cms_upsert_uses_file_kind_only() -> None:
    text = _require_sibling(AUTHOR_CMS_TS).read_text(encoding="utf-8")
    # buildProjectTreePayload hard-codes kind: "file" for README + index.js
    assert 'kind: "file"' in text
    assert 'kind: "readme"' not in text
    assert 'kind: "starter"' not in text


def test_content_validator_reexports_match_curriculum_enums() -> None:
    assert KNOWN_LESSON_STACKS == LESSON_STACKS
    assert KNOWN_RUNNER_KINDS == RUNNER_KINDS
    assert KNOWN_RUN_DEPENDENCY_KINDS == RUN_DEPENDENCY_KINDS
    assert KNOWN_PROJECT_FILE_KINDS == PROJECT_FILE_KINDS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("file", "file"),
        ("dir", "dir"),
        ("readme", "file"),
        ("starter", "file"),
        ("solution", "file"),
    ],
)
def test_normalize_project_file_kind_maps_harness_to_backend(raw: str, expected: str) -> None:
    assert normalize_project_file_kind(raw, path="x", content="y") == expected
    assert expected in PROJECT_FILE_KINDS


def test_validators_reject_values_not_in_backend_or_frontend() -> None:
    assert not validate_lesson_stack("cobol").ok
    assert not validate_test_boilerplate(
        {"body": "{{LEARNER_CODE}}", "runner_kind": "browser", "stack": "javascript"}
    ).ok
    assert not validate_run_dependencies([{"name": "lodash", "kind": "jar"}]).ok
    # harness alias remaps; validation of files still succeeds after normalize
    report = validate_project_files_for_rpc(
        [{"path": "README.md", "kind": "readme", "content": "# x"}]
    )
    assert report.ok

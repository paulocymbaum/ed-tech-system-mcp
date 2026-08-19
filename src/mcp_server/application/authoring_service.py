"""Application service for lesson bundle save + RPC payload mapping (E6)."""

from __future__ import annotations

import json
from typing import Any

from mcp_server.domain.authoring import AuthoringBackendPort, SaveLessonResult
from mcp_server.domain.content_validators import (
    validate_lesson_bundle,
    validate_lesson_stack,
    validate_project_files_for_rpc,
    validate_project_readme,
    validate_project_tests_json,
    validate_quiz_payload,
    validate_run_dependencies,
    validate_test_boilerplate,
)
from mcp_server.domain.curriculum_enums import normalize_project_file_kind
from mcp_server.domain.exceptions import DomainValidationError
from mcp_server.domain.harness_schemas import (
    HarnessLessonDraft,
    HarnessProjectDraft,
    HarnessQuizDraft,
)


def harness_quiz_to_rpc_payload(quiz: dict[str, Any] | HarnessQuizDraft) -> dict[str, Any]:
    """Map EdHarness quiz JSON to ``upsert_quiz_tree`` body."""
    data = quiz.model_dump(by_alias=True) if isinstance(quiz, HarnessQuizDraft) else quiz
    questions_out: list[dict[str, Any]] = []
    for position, question in enumerate(data.get("questions") or [], start=1):
        if not isinstance(question, dict):
            continue
        options_out: list[dict[str, Any]] = []
        for opt_pos, option in enumerate(question.get("options") or [], start=1):
            if not isinstance(option, dict):
                continue
            opt_slug = str(option.get("id") or option.get("slug") or "").strip()
            if not opt_slug:
                continue
            options_out.append(
                {
                    "slug": opt_slug,
                    "position": opt_pos,
                    "text": option.get("text"),
                }
            )
        slugs = [str(o["slug"]) for o in options_out if o.get("slug")]
        raw_correct = str(
            question.get("correctOptionId") or question.get("correct_option_slug") or ""
        ).strip()
        correct = next((slug for slug in slugs if slug == raw_correct), None)
        if correct is None and raw_correct:
            correct = next(
                (slug for slug in slugs if slug.lower() == raw_correct.lower()),
                None,
            )
        if len(slugs) < 2 or not correct:
            continue
        questions_out.append(
            {
                "slug": question.get("id") or question.get("slug"),
                "position": position,
                "prompt": question.get("prompt"),
                "explanation": question.get("explanation"),
                "correct_option_slug": correct,
                "options": options_out,
            }
        )
    quiz_id = data.get("id") or "quiz"
    return {
        "slug": quiz_id,
        "title": data.get("title"),
        "description": data.get("description"),
        "graph_index": data.get("graphIndex") or data.get("graph_index"),
        "source_path": f"lessons/{data.get('lessonId') or 'lesson'}/quiz/{quiz_id}.json",
        "questions": questions_out,
    }


def _rpc_project_file_kind(
    kind: object,
    *,
    path: str = "",
    content: object = None,
) -> str:
    """Map harness file labels to ``curriculum.project_file_kind`` (``dir`` | ``file``)."""
    return normalize_project_file_kind(kind, path=path, content=content)


def harness_project_to_rpc_payload(project: dict[str, Any] | HarnessProjectDraft) -> dict[str, Any]:
    """Map EdHarness project draft to ``upsert_project_tree`` body."""
    data = project.model_dump() if isinstance(project, HarnessProjectDraft) else project
    files_out: list[dict[str, Any]] = []
    for item in data.get("files") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        content = item.get("content")
        files_out.append(
            {
                "path": path,
                "kind": _rpc_project_file_kind(
                    item.get("kind"), path=str(path or ""), content=content
                ),
                "content": content,
            }
        )
    tests_out: list[dict[str, Any]] = []
    for position, case in enumerate(data.get("test_cases") or data.get("testCases") or [], start=1):
        if not isinstance(case, dict):
            continue
        tests_out.append(
            {
                "slug": case.get("id") or case.get("slug"),
                "name": case.get("name"),
                "stdin": case.get("stdin") or "",
                "expected_stdout": case.get("expectedStdout") or case.get("expected_stdout"),
                "expected_exit_code": case.get("expectedExitCode")
                or case.get("expected_exit_code"),
                "position": position,
            }
        )
    if not tests_out:
        tests_raw = ""
        for item in files_out:
            path = str(item.get("path") or "")
            if path.endswith("tests.json") and item.get("content"):
                tests_raw = str(item.get("content") or "")
                break
        if tests_raw:
            try:
                parsed: Any = json.loads(tests_raw)
            except json.JSONDecodeError:
                parsed = None
            cases = (
                parsed
                if isinstance(parsed, list)
                else parsed.get("cases")
                if isinstance(parsed, dict)
                else None
            )
            if isinstance(cases, list):
                for position, case in enumerate(cases, start=1):
                    if not isinstance(case, dict):
                        continue
                    tests_out.append(
                        {
                            "slug": case.get("id") or case.get("slug") or f"case-{position}",
                            "name": case.get("name") or f"case-{position}",
                            "stdin": case.get("stdin") or "",
                            "expected_stdout": case.get("expectedStdout")
                            or case.get("expected_stdout"),
                            "expected_exit_code": case.get("expectedExitCode")
                            or case.get("expected_exit_code"),
                            "position": position,
                        }
                    )
    readme = data.get("readme_markdown") or data.get("readmeMarkdown") or ""
    if readme and not any(f.get("path") == "README.md" for f in files_out):
        files_out.insert(0, {"path": "README.md", "kind": "file", "content": readme})
    return {
        "slug": data.get("slug"),
        "title": data.get("title"),
        "graph_index": data.get("graph_index") or data.get("graphIndex"),
        "root_path": data.get("root_path") or data.get("rootPath"),
        "files": files_out,
        "test_cases": tests_out,
    }


def _dump_project_test_cases(cases: list[Any]) -> str:
    """Serialize structured test_cases into starter/tests.json body."""
    out: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        row: dict[str, Any] = {
            "id": case.get("id") or case.get("slug"),
            "name": case.get("name"),
            "stdin": case.get("stdin") or "",
        }
        stdout = case.get("expectedStdout")
        if stdout is None:
            stdout = case.get("expected_stdout")
        if stdout is not None:
            row["expectedStdout"] = stdout
        exit_code = case.get("expectedExitCode")
        if exit_code is None:
            exit_code = case.get("expected_exit_code")
        if exit_code is not None:
            row["expectedExitCode"] = exit_code
        out.append(row)
    return json.dumps(out, indent=2)


def repair_invalid_project_tests_json(project: dict[str, Any]) -> list[str]:
    """Rewrite invalid starter/tests.json from structured test_cases when possible.

    LLM drafts often embed unescaped quotes in stdin strings, breaking the file
    JSON while still producing valid structured ``test_cases``.
    """
    cases = project.get("test_cases") or project.get("testCases")
    if not isinstance(cases, list) or not cases:
        return []
    files = project.get("files")
    if not isinstance(files, list):
        return []
    for item in files:
        if not isinstance(item, dict) or item.get("path") != "starter/tests.json":
            continue
        raw = str(item.get("content") or "")
        if not raw.strip():
            item["content"] = _dump_project_test_cases(cases)
            return [
                "warn: starter/tests.json was empty; filled from structured test_cases",
            ]
        try:
            json.loads(raw)
            return []
        except json.JSONDecodeError:
            item["content"] = _dump_project_test_cases(cases)
            return [
                "warn: starter/tests.json is not valid JSON; "
                "repaired from structured test_cases",
            ]
    return []


def harness_lesson_fields(
    lesson: dict[str, Any] | HarnessLessonDraft,
) -> tuple[str, dict[str, Any]]:
    """Extract readme markdown and meta dict from harness lesson."""
    if isinstance(lesson, HarnessLessonDraft):
        return lesson.readme_markdown, lesson.meta.model_dump(by_alias=True)
    readme = lesson.get("readme_markdown") or lesson.get("readmeMarkdown") or ""
    meta_raw = lesson.get("meta") or {}
    meta = dict(meta_raw) if isinstance(meta_raw, dict) else {}
    # Validators + upsert expect camelCase graph keys (aliases).
    if meta.get("graphIndex") is None and meta.get("graph_index") is not None:
        meta["graphIndex"] = meta["graph_index"]
    if meta.get("graphNodeId") is None and meta.get("graph_node_id") is not None:
        meta["graphNodeId"] = meta["graph_node_id"]
    return str(readme), meta


class AuthoringService:
    """Validate bundles and persist via ``AuthoringBackendPort``."""

    def __init__(self, backend: AuthoringBackendPort) -> None:
        self._backend = backend

    async def save_lesson_bundle(
        self,
        *,
        module_id: str,
        lesson_slug: str,
        lesson: dict[str, Any],
        quiz: dict[str, Any] | None = None,
        project: dict[str, Any] | None = None,
        publish: bool = False,
        skip_validation: bool = False,
        strict_project_readme_sections: bool = True,
    ) -> SaveLessonResult:
        readme, meta = harness_lesson_fields(lesson)
        project_readme = None
        project_tests = None
        if project:
            repair_invalid_project_tests_json(project)
            project_readme = project.get("readme_markdown") or project.get("readmeMarkdown")
            for item in project.get("files") or []:
                if isinstance(item, dict) and item.get("path") == "starter/tests.json":
                    project_tests = item.get("content")
                    break
            if project_tests is None and project.get("test_cases"):
                project_tests = json.dumps({"cases": project.get("test_cases")})

        if not skip_validation:
            report = validate_lesson_bundle(
                readme_markdown=readme,
                meta=meta,
                quiz=quiz,
                project_readme=project_readme,
                project_tests_json=project_tests,
                strict_project_readme_sections=strict_project_readme_sections,
            )
            if not report.ok:
                messages = [f"{f.level}: {f.message}" for f in report.errors]
                raise DomainValidationError("; ".join(messages))

        title = str(meta.get("title") or lesson_slug)
        lesson_id = await self._backend.upsert_lesson(
            module_id=module_id,
            slug=lesson_slug,
            title=title,
            description=meta.get("description"),
            graph_index=meta.get("graphIndex") or meta.get("graph_index"),
            graph_node_id=meta.get("graphNodeId") or meta.get("graph_node_id"),
        )
        source_path = f"lessons/{lesson_slug}/README.md"
        await self._backend.upsert_lesson_content_document(
            lesson_id=lesson_id,
            readme_markdown=readme,
            source_path=source_path,
        )

        quiz_id: str | None = None
        if quiz is not None:
            quiz_id = await self._backend.upsert_quiz_tree(
                lesson_id=lesson_id,
                quiz=harness_quiz_to_rpc_payload(quiz),
            )

        project_id: str | None = None
        if project is not None:
            boilerplate = project.get("test_boilerplate") or project.get("testBoilerplate")
            if isinstance(boilerplate, dict):
                bp_report = validate_test_boilerplate(boilerplate)
                if not bp_report.ok:
                    messages = [f"{f.level}: {f.message}" for f in bp_report.errors]
                    raise DomainValidationError("; ".join(messages))
            project_id = await self._backend.upsert_project_tree(
                lesson_id=lesson_id,
                project=harness_project_to_rpc_payload(project),
            )
            stack = str(
                meta.get("stack")
                or project.get("stack")
                or "javascript"
            )
            stack_report = validate_lesson_stack(stack)
            if not stack_report.ok:
                messages = [f"{f.level}: {f.message}" for f in stack_report.errors]
                raise DomainValidationError("; ".join(messages))
            deps = project.get("run_dependencies") or project.get("runDependencies") or []
            deps_report = validate_run_dependencies(deps)
            if not deps_report.ok:
                messages = [f"{f.level}: {f.message}" for f in deps_report.errors]
                raise DomainValidationError("; ".join(messages))
            await self._backend.set_lesson_stack_runtime(
                lesson_id=lesson_id,
                stack=stack,
                test_boilerplate_id=(
                    boilerplate.get("id") if isinstance(boilerplate, dict) else None
                ),
                boilerplate_slug=(
                    boilerplate.get("slug") if isinstance(boilerplate, dict) else None
                ),
                run_config=project.get("run_config") or project.get("runConfig") or {},
                dependencies=deps if isinstance(deps, list) else [],
                project_id=project_id,
            )

        published = False
        if publish:
            await self._backend.publish_lesson(lesson_id=lesson_id)
            published = True

        return SaveLessonResult(
            lesson_id=lesson_id,
            quiz_id=quiz_id,
            project_id=project_id,
            published=published,
        )


def validate_quiz_dict(quiz: dict[str, Any]) -> list[str]:
    report = validate_quiz_payload(quiz)
    return [f"{f.level}: {f.message}" for f in report.findings]


def validate_project_dict(
    project: dict[str, Any], *, strict_readme_sections: bool = True
) -> list[str]:
    repair_findings = repair_invalid_project_tests_json(project)
    readme = project.get("readme_markdown") or project.get("readmeMarkdown") or ""
    report = validate_project_readme(
        readme, required_sections_as_errors=strict_readme_sections
    )
    tests_raw = ""
    for item in project.get("files") or []:
        if isinstance(item, dict) and item.get("path") == "starter/tests.json":
            tests_raw = str(item.get("content") or "")
            break
    if tests_raw:
        report.findings.extend(validate_project_tests_json(tests_raw).findings)
    elif project.get("test_cases"):
        report.findings.extend(
            validate_project_tests_json(json.dumps({"cases": project.get("test_cases")})).findings
        )
    boilerplate = project.get("test_boilerplate") or project.get("testBoilerplate")
    if isinstance(boilerplate, dict):
        report.findings.extend(validate_test_boilerplate(boilerplate).findings)
    stack = project.get("stack")
    report.findings.extend(validate_lesson_stack(stack).findings)
    report.findings.extend(validate_project_files_for_rpc(project.get("files")).findings)
    deps = project.get("run_dependencies") or project.get("runDependencies")
    report.findings.extend(validate_run_dependencies(deps).findings)
    return repair_findings + [f"{f.level}: {f.message}" for f in report.findings]


def validate_lesson_dict(
    lesson: dict[str, Any], *, quiz: dict[str, Any] | None = None
) -> list[str]:
    readme, meta = harness_lesson_fields(lesson)
    report = validate_lesson_bundle(readme_markdown=readme, meta=meta, quiz=quiz)
    return [f"{f.level}: {f.message}" for f in report.findings]

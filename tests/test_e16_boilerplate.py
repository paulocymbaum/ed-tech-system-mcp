from mcp_server.application.authoring_service import harness_project_to_rpc_payload
from mcp_server.domain.content_validators import validate_test_boilerplate


def test_validate_test_boilerplate_requires_placeholder() -> None:
    report = validate_test_boilerplate({"body": "nope", "runner_kind": "browser-js"})
    assert report.ok is False


def test_validate_test_boilerplate_rejects_unknown_runner() -> None:
    report = validate_test_boilerplate(
        {"body": "{{LEARNER_CODE}}", "runner_kind": "cobol-batch"}
    )
    assert report.ok is False
    assert any("unknown runner_kind" in f.message for f in report.errors)


def test_validate_test_boilerplate_ok() -> None:
    report = validate_test_boilerplate(
        {"body": "{{LEARNER_CODE}}\n", "runnerKind": "browser-js", "stack": "javascript"}
    )
    assert report.ok is True


def test_harness_project_maps_starter_tests_json() -> None:
    payload = harness_project_to_rpc_payload(
        {
            "slug": "p1",
            "title": "P",
            "root_path": "course/p1",
            "files": [
                {
                    "path": "starter/tests.json",
                    "kind": "file",
                    "content": '{"cases":[{"id":"c1","name":"n","stdin":"1","expectedStdout":"2"}]}',
                }
            ],
        }
    )
    assert payload["test_cases"][0]["slug"] == "c1"
    assert payload["test_cases"][0]["expected_stdout"] == "2"


def test_harness_project_maps_file_kinds_to_db_enum() -> None:
    payload = harness_project_to_rpc_payload(
        {
            "slug": "p1",
            "title": "P",
            "root_path": "course/p1",
            "readme_markdown": "# Title\n\n## Goal\n\nShip it.\n",
            "files": [
                {"path": "starter", "kind": "dir", "content": None},
                {"path": "starter/index.js", "kind": "starter", "content": "console.log(1)\n"},
                {"path": "notes.md", "kind": "readme", "content": "# Notes\n"},
            ],
        }
    )
    by_path = {f["path"]: f["kind"] for f in payload["files"]}
    assert by_path["README.md"] == "file"
    assert by_path["starter"] == "dir"
    assert by_path["starter/index.js"] == "file"
    assert by_path["notes.md"] == "file"
    assert set(by_path.values()) <= {"dir", "file"}

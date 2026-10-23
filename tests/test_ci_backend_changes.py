import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import check_backend_changes as changes


@pytest.mark.parametrize(
    "paths",
    [
        ["web/src/app/App.tsx"],
        ["web/package-lock.json", "web/Dockerfile"],
        ["docs/payments.md", "README.md"],
        ["web/src/app/App.tsx", ".github/workflows/frontend.yml", "README.md"],
        ["web/file with spaces\nand a newline.tsx"],
        [],
    ],
)
def test_web_and_documentation_changes_skip_backend(paths: list[str]) -> None:
    assert not changes.requires_backend(paths)


@pytest.mark.parametrize(
    "path",
    [
        "apps/payments/services.py",
        "config/settings.py",
        "tests/test_patients.py",
        "requirements.lock",
        "pyproject.toml",
        "Dockerfile",
        ".dockerignore",
        "compose.yaml",
        "compose.frontend.yaml",
        ".github/workflows/ci.yml",
        ".github/workflows/discord.yml",
        "scripts/check_backend_changes.py",
        "scripts/notify_discord.py",
        "new-backend-directory/module.py",
        "tests/fixtures/document.md",
        "docs.py",
        "web.py",
    ],
)
def test_other_files_keep_backend_validation_even_with_web_changes(path: str) -> None:
    assert changes.requires_backend(["web/src/app/App.tsx", "docs/guide.md", path])


@pytest.mark.parametrize("event_name", ["pull_request", "push"])
@pytest.mark.parametrize(
    ("diff", "required"),
    [
        (b"web/src/App.tsx\0docs/guide.md\0", False),
        (b"apps/service.py\0web/service.py\0", True),
        (b"web/old.tsx\0apps/new.py\0", True),
        (b"web/file\nwith-newline.tsx\0", False),
        (b"tests/file\nweb/guide.md\0", True),
        (b"", False),
    ],
)
def test_event_comparison_classifies_changed_paths(
    monkeypatch, event_name: str, diff: bytes, required: bool
) -> None:
    def git_run(*args, **kwargs):
        return SimpleNamespace(stdout=diff)

    monkeypatch.setattr(changes.subprocess, "run", git_run)
    event = {"before": "a" * 40, "pull_request": {"base": {"sha": "b" * 40}}}
    assert changes.backend_required(event_name, event) is required


@pytest.mark.parametrize(
    ("event_name", "event"),
    [
        ("workflow_dispatch", {}),
        ("unknown", {}),
        ("push", {"before": "0" * 40}),
        ("push", {"before": "--upload-pack=bad"}),
        ("push", {"before": None}),
        ("pull_request", {}),
        ("pull_request", {"pull_request": {"base": {"sha": "invalid"}}}),
    ],
)
def test_manual_and_uncomparable_events_run_full_validation(
    monkeypatch, event_name: str, event: dict
) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("No git command should run without a valid comparison commit.")

    monkeypatch.setattr(changes.subprocess, "run", forbidden)
    assert changes.backend_required(event_name, event)


@pytest.mark.parametrize("failed_command", ["fetch", "diff"])
@pytest.mark.parametrize(
    "error",
    [
        OSError("git unavailable"),
        subprocess.CalledProcessError(1, "git"),
        subprocess.TimeoutExpired("git", 30),
    ],
)
def test_git_failures_keep_full_validation(monkeypatch, failed_command, error) -> None:
    def git_run(command, **kwargs):
        if command[1] == failed_command:
            raise error
        return SimpleNamespace(stdout=b"web/src/App.tsx\0")

    monkeypatch.setattr(changes.subprocess, "run", git_run)
    assert changes.backend_required("push", {"before": "a" * 40})


@pytest.mark.parametrize(("required", "value"), [(True, "true"), (False, "false")])
def test_cli_appends_a_boolean_step_output(
    monkeypatch, tmp_path, required, value
) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"before": "a" * 40}), encoding="utf-8")
    output_path = tmp_path / "output"
    output_path.write_text("existing=value\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    monkeypatch.setattr(changes, "backend_required", lambda *args: required)
    assert changes.main() == 0
    assert output_path.read_text(encoding="utf-8") == (
        f"existing=value\nrequired={value}\n"
    )


@pytest.mark.parametrize("event_text", ['{"invalid json"', "null", "[]"])
def test_unreadable_event_keeps_full_validation(
    monkeypatch, tmp_path, event_text
) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(event_text, encoding="utf-8")
    output_path = tmp_path / "output"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    assert changes.main() == 0
    assert output_path.read_text(encoding="utf-8") == "required=true\n"

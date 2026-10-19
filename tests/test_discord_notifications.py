import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from scripts import notify_discord as discord

WEBHOOK = "https://discord.com/api/webhooks/123456/fake-test-token"


@pytest.fixture
def pr_event() -> dict:
    return {
        "action": "opened",
        "repository": {"full_name": "owner/clinicflow"},
        "sender": {"login": "maintainer"},
        "pull_request": {
            "number": 12,
            "title": "Add clinic items",
            "user": {"login": "contributor"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/items"},
            "draft": False,
            "merged": False,
            "body": "PRIVATE BODY MUST NOT BE SENT",
        },
    }


@pytest.fixture
def run_event() -> dict:
    return {
        "action": "completed",
        "repository": {"full_name": "owner/clinicflow"},
        "workflow_run": {
            "id": 456,
            "name": "CI",
            "conclusion": "failure",
            "event": "pull_request",
            "head_branch": "feature/items",
            "head_sha": "a" * 40,
            "head_repository": {"full_name": "outsider/clinicflow"},
            "pull_requests": [{"number": 12}],
            "run_attempt": 2,
        },
    }


@pytest.mark.parametrize(
    ("action", "merged", "label"),
    [
        ("opened", False, "aberta"),
        ("reopened", False, "reaberta"),
        ("ready_for_review", False, "pronta para revisão"),
        ("closed", True, "mergeada"),
        ("closed", False, "encerrada"),
    ],
)
def test_pr_events_have_relevant_metadata_without_body_or_mentions(
    pr_event: dict, action: str, merged: bool, label: str
) -> None:
    pr_event["action"] = action
    pr_event["pull_request"]["merged"] = merged
    payload = discord.notification("pull_request_target", pr_event)
    embed = payload["embeds"][0]
    assert embed["title"] == f"PR #12 {label}"
    assert embed["url"] == "https://github.com/owner/clinicflow/pull/12"
    assert embed["description"] == "Add clinic items"
    assert {entry["name"]: entry["value"] for entry in embed["fields"]} == {
        "Repositório": "owner/clinicflow",
        "Autor": "contributor",
        "Ação por": "maintainer",
        "Branch": "feature/items",
        "Destino": "main",
    }
    assert payload["allowed_mentions"] == {"parse": []}
    assert "PRIVATE BODY" not in json.dumps(payload)


def test_draft_pr_is_identified(pr_event: dict) -> None:
    pr_event["pull_request"]["draft"] = True
    payload = discord.notification("pull_request_target", pr_event)
    assert payload["embeds"][0]["title"].endswith("(rascunho)")


@pytest.mark.parametrize("action", ["edited", "synchronize", "assigned"])
def test_ordinary_pr_updates_are_not_notified(pr_event: dict, action: str) -> None:
    pr_event["action"] = action
    assert discord.notification("pull_request_target", pr_event) is None


def test_pr_targeting_another_branch_is_ignored(pr_event: dict) -> None:
    pr_event["pull_request"]["base"]["ref"] = "other"
    assert discord.notification("pull_request_target", pr_event) is None


@pytest.mark.parametrize(
    "conclusion",
    ["failure", "timed_out", "action_required", "startup_failure", "stale"],
)
def test_ci_failure_metadata_is_available_even_for_fork_prs(
    run_event: dict, conclusion: str
) -> None:
    run_event["workflow_run"]["conclusion"] = conclusion
    payload = discord.notification("workflow_run", run_event)
    embed = payload["embeds"][0]
    assert embed["title"] == "CI precisa de atenção"
    assert embed["url"] == "https://github.com/owner/clinicflow/actions/runs/456"
    fields = {entry["name"]: entry["value"] for entry in embed["fields"]}
    assert fields["Resultado"] == conclusion.replace("_", r"\_")
    assert fields["PR"] == "#12"
    assert fields["Tentativa"] == "2"
    assert fields["Commit"] == "a" * 12


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
def test_successful_main_ci_is_notified(run_event: dict, event: str) -> None:
    run_event["workflow_run"].update(
        conclusion="success",
        event=event,
        head_branch="main",
        head_repository={"full_name": "owner/clinicflow"},
    )
    assert discord.notification("workflow_run", run_event)["embeds"][0]["title"] == (
        "CI aprovado na main"
    )


@pytest.mark.parametrize("conclusion", ["cancelled", "skipped", "neutral", "success"])
def test_cancelled_or_uninteresting_ci_results_are_ignored(
    run_event: dict, conclusion: str
) -> None:
    run_event["workflow_run"]["conclusion"] = conclusion
    assert discord.notification("workflow_run", run_event) is None


def test_fork_branch_named_main_does_not_qualify_for_success(run_event: dict) -> None:
    run_event["workflow_run"].update(
        conclusion="success", event="pull_request", head_branch="main"
    )
    assert discord.notification("workflow_run", run_event) is None


def test_other_workflows_are_ignored(run_event: dict) -> None:
    run_event["workflow_run"]["name"] = "Discord notifications"
    assert discord.notification("workflow_run", run_event) is None


def test_in_progress_workflow_is_ignored(run_event: dict) -> None:
    run_event["action"] = "in_progress"
    assert discord.notification("workflow_run", run_event) is None


def test_manual_event_creates_connection_test(pr_event: dict) -> None:
    payload = discord.notification("workflow_dispatch", pr_event)
    assert payload["embeds"][0]["title"] == "Discord conectado ao ClinicFlow"
    assert payload["allowed_mentions"] == {"parse": []}


def test_long_untrusted_metadata_stays_bounded_and_is_only_json_data(
    pr_event: dict,
) -> None:
    raw = '@everyone <@123> "quoted" `$(not-a-command)` **text** ' * 500
    pr_event["pull_request"]["title"] = raw
    pr_event["pull_request"]["head"]["ref"] = raw
    pr_event["pull_request"]["user"]["login"] = raw
    payload = discord.notification("pull_request_target", pr_event)
    embed = payload["embeds"][0]
    assert len(embed["description"]) <= 1000
    assert all(len(entry["value"]) <= 200 for entry in embed["fields"])
    assert r"\`" in embed["description"]
    assert payload["allowed_mentions"] == {"parse": []}
    assert json.loads(json.dumps(payload)) == payload
    assert (
        sum(
            len(value.encode("utf-16-le")) // 2
            for value in [embed["title"], embed["description"]]
            + [
                value
                for entry in embed["fields"]
                for value in (entry["name"], entry["value"])
            ]
        )
        < 6000
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (WEBHOOK, WEBHOOK + "?wait=true"),
        (WEBHOOK + "?wait=false", WEBHOOK + "?wait=true"),
        (WEBHOOK + "?thread_id=777", WEBHOOK + "?thread_id=777&wait=true"),
    ],
)
def test_valid_webhook_requests_confirmed_delivery(source: str, expected: str) -> None:
    assert discord.webhook_endpoint(source) == expected


@pytest.mark.parametrize(
    "url",
    [
        WEBHOOK.replace("https:", "http:"),
        WEBHOOK.replace("discord.com", "discord.com.example.test"),
        WEBHOOK.replace("discord.com", "example.test"),
        WEBHOOK.replace("discord.com", "user:password@discord.com"),
        WEBHOOK.replace("discord.com", "discord.com:444"),
        WEBHOOK + "/slack",
        WEBHOOK + "#fragment",
        WEBHOOK + "?extra=value",
        WEBHOOK + "?thread_id=not-a-number",
    ],
)
def test_webhook_configuration_is_restricted_to_discord(url: str) -> None:
    with pytest.raises(ValueError):
        discord.webhook_endpoint(url)


def test_post_uses_json_utf8_timeout_and_redirect_guard(monkeypatch) -> None:
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Opener:
        def open(self, request, *, timeout):
            captured.update(request=request, timeout=timeout)
            return Response()

    def opener(handler):
        assert isinstance(handler, discord.NoRedirect)
        return Opener()

    monkeypatch.setattr(discord, "build_opener", opener)
    payload = {"embeds": [{"title": "Ação"}], "allowed_mentions": {"parse": []}}
    discord.send(WEBHOOK, payload)
    request = captured["request"]
    assert request.method == "POST"
    assert request.full_url == WEBHOOK + "?wait=true"
    assert captured["timeout"] == 10
    assert json.loads(request.data.decode("utf-8")) == payload
    assert request.get_header("Content-type") == "application/json"
    assert (
        discord.NoRedirect().redirect_request(
            request, None, 302, "Found", {}, "https://example.test"
        )
        is None
    )


@pytest.fixture
def event_environment(monkeypatch, tmp_path, pr_event: dict) -> None:
    path = tmp_path / "event.json"
    path.write_text(json.dumps(pr_event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", WEBHOOK)


def test_missing_secret_skips_without_reading_event(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    assert discord.main() == 0
    assert "not configured" in capsys.readouterr().out


def test_cli_delivers_selected_event(monkeypatch, event_environment, capsys) -> None:
    sent = []
    monkeypatch.setattr(discord, "send", lambda url, payload: sent.append(payload))
    assert discord.main() == 0
    assert len(sent) == 1
    assert "delivered" in capsys.readouterr().out


def test_skipped_event_does_not_contact_discord(monkeypatch, event_environment) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "other")

    def forbidden(*args):
        pytest.fail("Skipped events must not contact Discord.")

    monkeypatch.setattr(discord, "send", forbidden)
    assert discord.main() == 0


@pytest.mark.parametrize("status", [302, 400, 401, 404, 429, 500])
def test_http_errors_never_log_webhook_or_response_body(
    monkeypatch, event_environment, capsys, status: int
) -> None:
    def fail(*args):
        raise HTTPError(WEBHOOK, status, WEBHOOK, {}, BytesIO(WEBHOOK.encode()))

    monkeypatch.setattr(discord, "send", fail)
    assert discord.main() == 1
    output = capsys.readouterr()
    assert f"HTTP {status}" in output.err
    assert WEBHOOK not in output.err + output.out
    assert "fake-test-token" not in output.err + output.out


def test_network_exception_details_are_not_logged(
    monkeypatch, event_environment, capsys
):
    def fail(*args):
        raise URLError(WEBHOOK)

    monkeypatch.setattr(discord, "send", fail)
    assert discord.main() == 1
    output = capsys.readouterr()
    assert WEBHOOK not in output.err + output.out
    assert "Could not prepare or deliver" in output.err

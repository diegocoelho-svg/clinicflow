"""Send selected GitHub event metadata to Discord using only the standard library."""

import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MARKDOWN = re.compile(r"([\\`*_{}\[\]()<>|])")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
WEBHOOK_PATH = re.compile(r"/api(?:/v[0-9]+)?/webhooks/[0-9]+/[A-Za-z0-9._-]+/?")
FAILURES = {"failure", "timed_out", "action_required", "startup_failure", "stale"}


def text(value: object, limit: int = 200) -> str:
    """Flatten and escape display metadata; never treat event text as instructions."""
    value = " ".join(str(value).split())
    return MARKDOWN.sub(r"\\\1", value)[:limit] or "-"


def number(value: object) -> int:
    if isinstance(value, bool) or not str(value).isascii() or not str(value).isdigit():
        raise ValueError("Expected a positive event identifier.")
    parsed = int(value)
    if parsed < 1:
        raise ValueError("Expected a positive event identifier.")
    return parsed


def field(name: str, value: object) -> dict:
    return {"name": name, "value": text(value, 200), "inline": True}


def notification(event_name: str, event: dict) -> dict | None:
    repository = event["repository"]["full_name"]
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise ValueError("Invalid repository name.")
    repository_url = f"https://github.com/{repository}"
    fields = [field("Repositório", repository)]

    if event_name == "pull_request_target":
        pr = event["pull_request"]
        if pr["base"]["ref"] != "main":
            return None
        action = event["action"]
        actions = {
            "opened": ("aberta", 0x2DA44E),
            "reopened": ("reaberta", 0x2DA44E),
            "ready_for_review": ("pronta para revisão", 0x0969DA),
            "closed": ("mergeada" if pr.get("merged") else "encerrada", 0x8957E5),
        }
        if action not in actions:
            return None
        label, color = actions[action]
        pr_number = number(pr["number"])
        title = f"PR #{pr_number} {label}"
        if pr.get("draft"):
            title += " (rascunho)"
        description = text(pr["title"], 1000)
        url = f"{repository_url}/pull/{pr_number}"
        fields.extend(
            [
                field("Autor", pr["user"]["login"]),
                field("Ação por", event.get("sender", {}).get("login", "GitHub")),
                field("Branch", pr["head"]["ref"]),
                field("Destino", pr["base"]["ref"]),
            ]
        )
    elif event_name == "workflow_run":
        run = event["workflow_run"]
        if event.get("action") != "completed" or run["name"] != "CI":
            return None
        conclusion = run["conclusion"]
        if conclusion in FAILURES:
            title, color = "CI precisa de atenção", 0xCF222E
        elif (
            conclusion == "success"
            and run["head_branch"] == "main"
            and run["event"] in {"push", "workflow_dispatch"}
            and run["head_repository"]["full_name"] == repository
        ):
            title, color = "CI aprovado na main", 0x2DA44E
        else:
            return None
        description = "Resultado das verificações automáticas do ClinicFlow."
        url = f"{repository_url}/actions/runs/{number(run['id'])}"
        fields.extend(
            [
                field("Resultado", conclusion),
                field("Branch", run["head_branch"]),
                field("Commit", str(run["head_sha"])[:12]),
                field("Tentativa", number(run.get("run_attempt", 1))),
            ]
        )
        for pr in run.get("pull_requests", [])[:1]:
            fields.append(field("PR", f"#{number(pr['number'])}"))
    elif event_name == "workflow_dispatch":
        title, color = "Discord conectado ao ClinicFlow", 0x0969DA
        description = "Mensagem de teste enviada pelo workflow de notificações."
        url = f"{repository_url}/actions"
        fields.append(
            field("Solicitado por", event.get("sender", {}).get("login", "GitHub"))
        )
    else:
        return None

    return {
        "username": "ClinicFlow",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": title,
                "description": description,
                "url": url,
                "color": color,
                "fields": fields,
            }
        ],
    }


def webhook_endpoint(value: str) -> str:
    """Allow Discord HTTPS webhook endpoints, with confirmed delivery requested."""
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or url.hostname != "discord.com"
        or url.port not in {None, 443}
        or url.username is not None
        or url.password is not None
        or url.fragment
        or not WEBHOOK_PATH.fullmatch(url.path)
    ):
        raise ValueError("Invalid Discord webhook configuration.")
    query = dict(parse_qsl(url.query, keep_blank_values=True))
    if query.keys() - {"wait", "thread_id"}:
        raise ValueError("Unsupported webhook query configuration.")
    if "thread_id" in query:
        number(query["thread_id"])
    query["wait"] = "true"
    return urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ""))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(webhook_url: str, payload: dict) -> None:
    request = Request(
        webhook_endpoint(webhook_url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ClinicFlow-GitHub-Actions/1.0",
        },
        method="POST",
    )
    # No automatic POST retries: an uncertain response may already have been delivered.
    with build_opener(NoRedirect()).open(request, timeout=10) as response:
        if response.status != 200:
            raise ValueError("Discord did not confirm message delivery.")


def main() -> int:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL is not configured; skipping Discord notification.")
        return 0
    try:
        with Path(os.environ["GITHUB_EVENT_PATH"]).open(encoding="utf-8") as file:
            event = json.load(file)
        payload = notification(os.environ["GITHUB_EVENT_NAME"], event)
        if payload is None:
            print("This event does not require a Discord notification.")
            return 0
        send(webhook_url, payload)
    except HTTPError as error:
        print(f"Discord delivery failed (HTTP {error.code}).", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        # Exception text or HTTP response bodies may contain the secret webhook URL.
        print("Could not prepare or deliver the Discord notification.", file=sys.stderr)
        return 1
    print("Discord notification delivered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

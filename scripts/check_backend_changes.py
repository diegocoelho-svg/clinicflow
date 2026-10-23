"""Skip expensive backend checks only for changes known to be web or documentation."""

import json
import os
import re
import subprocess
from pathlib import Path

COMMIT = re.compile(r"[0-9a-f]{40,64}")
NON_BACKEND_FILES = {"README.md", ".github/workflows/frontend.yml"}


def requires_backend(paths: list[str]) -> bool:
    return any(
        path not in NON_BACKEND_FILES and not path.startswith(("web/", "docs/"))
        for path in paths
    )


def backend_required(event_name: str, event: dict) -> bool:
    if event_name == "workflow_dispatch":
        return True
    try:
        if event_name == "pull_request":
            base = event["pull_request"]["base"]["sha"]
        elif event_name == "push":
            base = event["before"]
        else:
            return True
        if (
            not isinstance(base, str)
            or not COMMIT.fullmatch(base)
            or set(base) == {"0"}
        ):
            return True
        # Fetch only the comparison commit; checkout intentionally has no credentials.
        subprocess.run(
            ["git", "fetch", "--no-tags", "--depth=1", "origin", base],
            check=True,
            capture_output=True,
            timeout=30,
        )
        result = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z", base, "HEAD"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        # Disabling rename detection includes both paths when a backend file moves
        # into web/docs. NUL separation preserves filenames containing newlines.
        paths = [path for path in os.fsdecode(result.stdout).split("\0") if path]
        return requires_backend(paths)
    except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError):
        print("Could not determine changed files; running full backend validation.")
        return True


def main() -> int:
    try:
        with Path(os.environ["GITHUB_EVENT_PATH"]).open(encoding="utf-8") as file:
            event = json.load(file)
        required = backend_required(os.environ["GITHUB_EVENT_NAME"], event)
    except (OSError, KeyError, TypeError, ValueError):
        print("Could not read the GitHub event; running full backend validation.")
        required = True
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as file:
        file.write(f"required={str(required).lower()}\n")
    print(
        "Backend validation required." if required else "Only web/docs files changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""File or update a GitHub issue per drifted source URL.

Reads the JSON output of `binwise check-sources --json`, filters for entries
in `changed` or `http_error` state, and ensures one open issue per URL with
the `source-changed` label. Idempotent: re-running on the same drift state
does not duplicate issues.
"""

from __future__ import annotations

import json
import subprocess
import sys


def gh(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=capture, text=True, check=check)


def ensure_label() -> None:
    # `gh label create` errors if the label exists; ignore that failure mode.
    subprocess.run(
        [
            "gh",
            "label",
            "create",
            "source-changed",
            "--description",
            "Upstream source content changed; re-verify or rebaseline",
            "--color",
            "FBCA04",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def open_issues_by_title() -> dict[str, int]:
    res = gh(
        "issue",
        "list",
        "--label",
        "source-changed",
        "--state",
        "open",
        "--limit",
        "200",
        "--json",
        "title,number",
        capture=True,
    )
    return {i["title"]: i["number"] for i in json.loads(res.stdout or "[]")}


def file_issue(diff: dict) -> None:
    cities = ", ".join(diff["cities"])
    title = f"source drift: {diff['url']}"
    body_lines = [
        "The upstream content at this URL has diverged from the committed baseline (or the fetch failed).",
        "",
        f"- URL: {diff['url']}",
        f"- Cities affected: {cities}",
        f"- State: `{diff['state']}`",
        f"- HTTP status: {diff['status']}",
        f"- Last successful check: {diff.get('last_checked') or '(never)'}",
    ]
    if diff.get("error"):
        body_lines.append(f"- Error: `{diff['error']}`")
    body_lines += [
        "",
        "## What to do",
        "",
        "1. Open the URL in a browser. Inspect the page against the affected city files.",
        "2. **Substantive rule change?** File a re-verification PR: update the city files, "
        "bump `last_verified`, save a fresh Wayback snapshot, then re-baseline with "
        "`binwise check-sources --update` and commit `.github/source-hashes.json`.",
        "3. **Cosmetic change only** (template / build / telemetry, rules unchanged)? "
        "Just run `binwise check-sources --update` and commit the baseline diff.",
        "",
        "This issue was filed automatically by `.github/workflows/source-change.yml`.",
    ]
    gh("issue", "create", "--label", "source-changed", "--title", title, "--body", "\n".join(body_lines))


def main(path: str) -> None:
    with open(path) as f:
        diffs = json.load(f)
    drifted = [d for d in diffs if d["state"] in ("changed", "http_error")]
    if not drifted:
        print("no drift; nothing to file")
        return

    ensure_label()
    existing = open_issues_by_title()

    filed = 0
    skipped = 0
    for d in drifted:
        title = f"source drift: {d['url']}"
        if title in existing:
            print(f"already open: #{existing[title]} — {title}")
            skipped += 1
            continue
        file_issue(d)
        print(f"filed: {title}")
        filed += 1

    print(f"summary: {filed} filed, {skipped} already-open")


if __name__ == "__main__":
    main(sys.argv[1])

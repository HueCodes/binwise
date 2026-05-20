from __future__ import annotations

import sys
from pathlib import Path

import click

from . import rules as rules_module
from .agent import sort_image


@click.group()
def main() -> None:
    """binwise: point your camera at trash, get a verdict."""


@main.command("sort")
@click.argument("image", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--city", required=True, help="City slug, e.g. san-francisco. See `binwise list-cities`.")
@click.option("--show-usage", is_flag=True, help="Print token usage and cache stats.")
def sort_cmd(image: Path, city: str, show_usage: bool) -> None:
    """Sort an image of one or more items."""
    try:
        rules = rules_module.load_city(city)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(2)

    result = sort_image(image, rules)
    items = result["items"]

    level = rules.get("verification_level")
    if level == "unverified":
        warning = (
            f"WARNING: '{rules.get('name')}' rules are unverified. "
            "Treat output as best-effort; confirm with your local hauler before relying on it."
        )
        click.echo(click.style(warning, fg="yellow"), err=True)
        click.echo("", err=True)

    if not items:
        click.echo("No items identified.")
        return

    bin_label = {b["id"]: b["label"] for b in rules["bins"]}
    bin_label["unknown"] = "unknown (not covered by city rules)"

    for i, entry in enumerate(items):
        if i:
            click.echo("")
        click.echo(f"ITEM:    {entry['item']}")
        click.echo(f"BIN:     {bin_label.get(entry['bin'], entry['bin'])}")
        if entry.get("prep"):
            click.echo(f"PREP:    {entry['prep']}")
        click.echo(f"WHY:     {entry['why']}")

    if show_usage:
        u = result["usage"]
        click.echo("")
        click.echo(
            f"[usage] input={u['input_tokens']} output={u['output_tokens']} "
            f"cache_write={u['cache_creation_input_tokens']} cache_read={u['cache_read_input_tokens']}"
        )

    click.echo("")
    click.echo(
        click.style(
            "binwise output is a guide, not authoritative. When in doubt, check your hauler's page directly.",
            fg="cyan",
        ),
        err=True,
    )


@main.command("list-cities")
def list_cities_cmd() -> None:
    """List cities with rulesets in this repo."""
    cities = rules_module.list_cities()
    if not cities:
        click.echo("No cities found. Add one at cities/<country>/<state>/<slug>.json (see CONTRIBUTING.md).")
        return
    for c in cities:
        click.echo(f"{c['slug']:30s}  {c['city']}, {c['state']}, {c['country']}")


@main.command("serve")
@click.option(
    "--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 to expose on the LAN (e.g. for phone testing)."
)
@click.option("--port", default=8000, type=int)
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev).")
def serve_cmd(host: str, port: int, reload: bool) -> None:
    """Run the web demo (browser + phone-friendly upload page at /)."""
    import uvicorn

    click.echo(
        click.style(
            "binwise reference demo. Output is a guide, not authoritative — when in doubt, check your hauler.",
            fg="cyan",
        )
    )
    uvicorn.run("binwise.web:app", host=host, port=port, reload=reload)


@main.command("validate")
def validate_cmd() -> None:
    """Validate every city file against the schema, taxonomy, and consistency rules."""
    from . import validate as v

    report = v.validate_all()

    by_file: dict = {}
    for issue in report.issues:
        by_file.setdefault(issue.path, []).append(issue)

    for path in sorted(by_file):
        rel = path.relative_to(v.REPO_ROOT)
        click.echo(str(rel))
        for issue in by_file[path]:
            color = "red" if issue.level == "error" else "yellow"
            tag = click.style(f"  {issue.level.upper():5s}", fg=color)
            click.echo(f"{tag} {issue.message}")

    n_err = len(report.errors)
    n_warn = len(report.warnings)
    summary = f"{report.files_checked} files checked, {n_err} errors, {n_warn} warnings"
    click.echo("")
    click.echo(click.style(summary, fg="red" if n_err else ("yellow" if n_warn else "green")))
    if n_err:
        raise SystemExit(1)


@main.command("format")
@click.option("--check", is_flag=True, help="Don't rewrite; exit nonzero if any file is not canonical.")
def format_cmd(check: bool) -> None:
    """Rewrite city files in canonical JSON form (sorted keys, 2-space indent, trailing newline)."""
    from . import validate as v

    if check:
        import json as _json

        non_canonical = []
        for path in v.format_targets():
            content = path.read_text()
            data = _json.loads(content)
            if content != v._canonical_json(data):
                non_canonical.append(path.relative_to(v.REPO_ROOT))
        for path in non_canonical:
            click.echo(f"not canonical: {path}", err=True)
        if non_canonical:
            raise SystemExit(1)
        click.echo("all files canonical")
        return

    changed = v.format_all()
    if not changed:
        click.echo("no changes")
        return
    for path in changed:
        click.echo(f"formatted: {path.relative_to(v.REPO_ROOT)}")


def _render_coverage_section() -> str:
    import json as _json
    from collections import Counter
    from urllib.parse import urlparse

    from . import validate as v

    cities = []
    for path in sorted(v.CITIES_DIR.rglob("*.json")):
        d = _json.loads(path.read_text())
        cities.append(d)

    counts = Counter(c["verification_level"] for c in cities)
    levels = ["resident_confirmed", "reviewed", "unverified"]
    summary_bits = [f"{counts.get(lv, 0)} {lv}" for lv in levels if counts.get(lv, 0)]
    summary = f"{len(cities)} cities — " + ", ".join(summary_bits) + "."

    rows = ["| City | Country / State | Verification | Last verified | Source |", "|---|---|---|---|---|"]
    for c in sorted(cities, key=lambda c: (c["country"], c.get("state") or "", c["name"])):
        host = urlparse(c["primary_source"]).netloc.removeprefix("www.")
        loc = f"{c['country']} / {c.get('state') or '-'}"
        rows.append(
            f"| {c['name']} | {loc} | `{c['verification_level']}` "
            f"| {c.get('last_verified', '')} | [{host}]({c['primary_source']}) |"
        )
    return summary + "\n\n" + "\n".join(rows)


def _splice_coverage_table(readme: str, section: str) -> str:
    start, end = "<!-- COVERAGE-TABLE:START -->", "<!-- COVERAGE-TABLE:END -->"
    if start not in readme or end not in readme:
        raise click.ClickException(f"README is missing the coverage-table markers ({start} ... {end})")
    head, _, rest = readme.partition(start)
    _, _, tail = rest.partition(end)
    return f"{head}{start}\n{section}\n{end}{tail}"


@main.command("coverage")
@click.option("--check", is_flag=True, help="Don't rewrite; exit nonzero if README's coverage table is stale.")
def coverage_cmd(check: bool) -> None:
    """Regenerate the auto-generated coverage table region in README.md."""
    from . import validate as v

    readme_path = v.REPO_ROOT / "README.md"
    current = readme_path.read_text()
    new = _splice_coverage_table(current, _render_coverage_section())
    if check:
        if new != current:
            click.echo("README coverage table is stale; run `binwise coverage` to regenerate.", err=True)
            raise SystemExit(1)
        click.echo("coverage table up to date")
        return
    if new == current:
        click.echo("no changes")
        return
    readme_path.write_text(new)
    click.echo("README coverage table regenerated")


@main.command("archive")
@click.argument("url")
def archive_cmd(url: str) -> None:
    """Save a URL to the Wayback Machine and print the dated snapshot URL."""
    from . import wayback

    try:
        snapshot = wayback.save(url)
    except wayback.ArchiveError as e:
        click.echo(f"archive failed: {e}", err=True)
        sys.exit(1)
    click.echo(snapshot)


@main.group()
def taxonomy() -> None:
    """Inspect the material taxonomy."""


@taxonomy.command("search")
@click.argument("term")
def taxonomy_search_cmd(term: str) -> None:
    """Search taxonomy categories by id, name, alias, or example."""
    import json as _json

    from . import validate as v

    data = _json.loads(v.TAXONOMY_PATH.read_text())
    q = term.lower()
    hits: list[tuple[int, dict]] = []
    for cat in data["categories"]:
        score = 0
        if cat["id"] == q:
            score = 100
        elif cat["name"].lower() == q:
            score = 90
        elif q in cat["id"] or q in cat["name"].lower():
            score = 50
        for alias in cat.get("aliases", []):
            al = alias.lower()
            if al == q:
                score = max(score, 70)
            elif q in al:
                score = max(score, 30)
        for example in cat.get("examples", []):
            if q in example.lower():
                score = max(score, 25)
        if score > 0:
            hits.append((score, cat))

    hits.sort(key=lambda x: (-x[0], x[1]["id"]))
    if not hits:
        click.echo(f"no matches for {term!r} in taxonomy.json", err=True)
        sys.exit(1)

    for _, cat in hits:
        click.echo(click.style(cat["id"], bold=True) + f"  {cat['name']}")
        if cat.get("aliases"):
            click.echo(f"  aliases: {', '.join(cat['aliases'])}")
        if cat.get("examples"):
            click.echo(f"  examples: {', '.join(cat['examples'])}")


@main.command("check-sources")
@click.option(
    "--update",
    is_flag=True,
    help="Treat current page hashes as the new baseline (rewrites .github/source-hashes.json).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON instead of human output.")
def check_sources_cmd(update: bool, as_json: bool) -> None:
    """Diff each city's primary_source against the baseline; alert on drift."""
    from . import source_check as sc

    diffs = sc.check(update=update)

    if as_json:
        click.echo(sc.diffs_to_json(diffs), nl=False)
    else:
        for d in diffs:
            cities = ", ".join(d.cities)
            if d.state == "unchanged":
                click.echo(f"  ok        {d.url}  ({cities})")
            elif d.state == "new":
                click.echo(click.style(f"  baselined {d.url}  ({cities})", fg="cyan"))
            elif d.state == "changed":
                color = "green" if update else "red"
                action = "rebaselined" if update else "DRIFT"
                click.echo(click.style(f"  {action:9s} {d.url}  ({cities})", fg=color))
            elif d.state == "http_error":
                click.echo(click.style(f"  ERROR     {d.url}  ({cities})  {d.error}", fg="red"))

    if not update and not as_json and sc.has_drift(diffs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

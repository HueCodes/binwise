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
        non_canonical = []
        for path in sorted(v.CITIES_DIR.rglob("*.json")):
            content = path.read_text()
            import json as _json

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


if __name__ == "__main__":
    main()

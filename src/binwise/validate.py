from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "v0.1.json"
TAXONOMY_SCHEMA_PATH = REPO_ROOT / "schema" / "taxonomy-v0.1.json"
TAXONOMY_PATH = REPO_ROOT / "taxonomy.json"
CITIES_DIR = REPO_ROOT / "cities"

KNOWN_HAULER_DOMAINS = {
    "recology.com",
    "wm.com",
    "republicservices.com",
    "casella.com",
    "wasteindustries.com",
    "rumpke.com",
    "wastemanagement.com",
}

# Municipal/public-agency sites that aren't on a .gov TLD but are city
# departments or state agencies. Treated as gov-equivalent for source
# classification at reviewed verification levels.
MUNICIPAL_DEPT_DOMAINS = {
    "sfenvironment.org",  # San Francisco Environment Department
}


@dataclass
class Issue:
    path: Path
    level: str
    message: str


@dataclass
class Report:
    files_checked: int = 0
    issues: list[Issue] = field(default_factory=list)

    def add(self, path: Path, level: str, msg: str) -> None:
        self.issues.append(Issue(path, level, msg))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warn"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _classify_source_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.endswith(".gov") or ".gov." in host:
        return "gov"
    bare = host[4:] if host.startswith("www.") else host
    if bare in MUNICIPAL_DEPT_DOMAINS:
        return "gov"
    for d in KNOWN_HAULER_DOMAINS:
        if bare == d or bare.endswith("." + d):
            return "hauler"
    return "other"


def _walk_sources(city: dict) -> Iterable[tuple[str, dict]]:
    """Yield (location_path, source_dict) for every source in a city file."""
    for i, rule in enumerate(city.get("rules", [])):
        if "source" in rule:
            yield (f"rules[{i}].source", rule["source"])
        for j, cond in enumerate(rule.get("conditions", []) or []):
            if "source" in cond:
                yield (f"rules[{i}].conditions[{j}].source", cond["source"])
    for i, ec in enumerate(city.get("edge_cases", []) or []):
        if "source" in ec:
            yield (f"edge_cases[{i}].source", ec["source"])


def _validate_one(path: Path, schema: dict, taxonomy_ids: set[str], report: Report) -> None:
    content = path.read_text()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        report.add(path, "error", f"invalid JSON: {e}")
        return

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        report.add(path, "error", f"schema: {loc}: {err.message}")

    if not data.get("rules"):
        report.add(path, "error", "rules array is empty; a city file with no rules has no value")

    seen_bin_ids: dict[str, int] = {}
    for i, b in enumerate(data.get("bins", [])):
        bid = b.get("id")
        if bid in seen_bin_ids:
            report.add(path, "error", f"bins[{i}].id {bid!r} duplicated (also at bins[{seen_bin_ids[bid]}])")
        elif bid:
            seen_bin_ids[bid] = i

    expected_slug = path.stem
    if data.get("slug") != expected_slug:
        report.add(
            path, "error", f"slug mismatch: filename is {expected_slug}.json, slug field is {data.get('slug')!r}"
        )

    rel = path.relative_to(CITIES_DIR)
    expected_country = rel.parts[0].upper() if len(rel.parts) >= 3 else None
    expected_state = rel.parts[1].upper() if len(rel.parts) >= 3 else None
    if expected_country and data.get("country") != expected_country:
        report.add(
            path,
            "error",
            f"country mismatch: directory is {expected_country!r}, country field is {data.get('country')!r}",
        )
    if expected_state and data.get("state") and data["state"] != expected_state:
        report.add(
            path, "error", f"state mismatch: directory is {expected_state!r}, state field is {data.get('state')!r}"
        )

    defined_bins = {b["id"] for b in data.get("bins", [])}
    for i, rule in enumerate(data.get("rules", [])):
        if rule.get("bin") not in (defined_bins | {"depends"}):
            report.add(path, "error", f"rules[{i}].bin {rule.get('bin')!r} not declared in bins")
        for j, cond in enumerate(rule.get("conditions", []) or []):
            if cond.get("then_bin") not in defined_bins:
                report.add(
                    path, "error", f"rules[{i}].conditions[{j}].then_bin {cond.get('then_bin')!r} not declared in bins"
                )
    for i, ec in enumerate(data.get("edge_cases", []) or []):
        if ec.get("bin") not in defined_bins:
            report.add(path, "error", f"edge_cases[{i}].bin {ec.get('bin')!r} not declared in bins")

    for i, rule in enumerate(data.get("rules", [])):
        cat = rule.get("category")
        if cat and cat not in taxonomy_ids:
            report.add(path, "error", f"rules[{i}].category {cat!r} not in taxonomy.json")

    seen_categories: dict[str, int] = {}
    for i, rule in enumerate(data.get("rules", [])):
        cat = rule.get("category")
        if cat in seen_categories:
            report.add(path, "error", f"rules[{i}].category {cat!r} duplicated (also at rules[{seen_categories[cat]}])")
        else:
            seen_categories[cat] = i

    level = data.get("verification_level")
    if level in ("reviewed", "resident_confirmed"):
        for loc, src in _walk_sources(data):
            kind = _classify_source_url(src.get("url", ""))
            if kind == "other":
                report.add(
                    path,
                    "warn",
                    f"verification_level={level} but {loc} URL is not .gov or known hauler: {src.get('url')!r}",
                )

    for loc, src in _walk_sources(data):
        archive_url = src.get("archive_url")
        if archive_url and urlparse(archive_url).netloc.lower() not in ("web.archive.org", "www.web.archive.org"):
            report.add(path, "error", f"{loc}.archive_url must be a web.archive.org URL: {archive_url!r}")

    today = date.today()
    last_v = data.get("last_verified")
    if last_v:
        try:
            d = date.fromisoformat(last_v)
            age_days = (today - d).days
            already_unverified = data.get("verification_level") == "unverified"
            if age_days < 0:
                report.add(path, "error", f"last_verified is in the future: {last_v}")
            elif age_days > 730 and not already_unverified:
                report.add(path, "error", f"last_verified is {age_days} days old (>24 months); auto-downgrade required")
            elif age_days > 365 and not already_unverified:
                report.add(path, "warn", f"last_verified is {age_days} days old (>12 months); needs re-verification")
        except ValueError:
            report.add(path, "error", f"last_verified is not a valid ISO date: {last_v!r}")

    for loc, src in _walk_sources(data):
        retrieved = src.get("retrieved")
        if not retrieved:
            continue
        try:
            r = date.fromisoformat(retrieved)
        except ValueError:
            report.add(path, "error", f"{loc}.retrieved is not a valid ISO date: {retrieved!r}")
            continue
        if (today - r).days < 0:
            report.add(path, "error", f"{loc}.retrieved is in the future: {retrieved}")

    if content != _canonical_json(data):
        report.add(path, "warn", "not in canonical JSON form; run `binwise format` to fix")

    report.files_checked += 1


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _load_taxonomy_schema() -> dict:
    return json.loads(TAXONOMY_SCHEMA_PATH.read_text())


def _load_taxonomy() -> dict:
    return json.loads(TAXONOMY_PATH.read_text())


def _validate_taxonomy(taxonomy: dict, taxonomy_schema: dict, report: Report) -> set[str]:
    Draft202012Validator.check_schema(taxonomy_schema)
    validator = Draft202012Validator(taxonomy_schema, format_checker=FormatChecker())
    for err in sorted(validator.iter_errors(taxonomy), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        report.add(TAXONOMY_PATH, "error", f"schema: {loc}: {err.message}")

    seen: dict[str, int] = {}
    ids: set[str] = set()
    for i, c in enumerate(taxonomy.get("categories", [])):
        cid = c.get("id")
        if cid in seen:
            report.add(
                TAXONOMY_PATH, "error", f"categories[{i}].id {cid!r} duplicated (also at categories[{seen[cid]}])"
            )
        elif cid:
            seen[cid] = i
            ids.add(cid)
    return ids


def validate_all() -> Report:
    schema = _load_schema()
    taxonomy_schema = _load_taxonomy_schema()
    taxonomy = _load_taxonomy()
    Draft202012Validator.check_schema(schema)
    report = Report()
    taxonomy_ids = _validate_taxonomy(taxonomy, taxonomy_schema, report)
    for path in sorted(CITIES_DIR.rglob("*.json")):
        _validate_one(path, schema, taxonomy_ids, report)
    return report


def format_all() -> list[Path]:
    changed: list[Path] = []
    for path in sorted(CITIES_DIR.rglob("*.json")):
        content = path.read_text()
        data = json.loads(content)
        canonical = _canonical_json(data)
        if content != canonical:
            path.write_text(canonical)
            changed.append(path)

    for extra in (TAXONOMY_PATH, SCHEMA_PATH, TAXONOMY_SCHEMA_PATH):
        if extra.exists():
            content = extra.read_text()
            data = json.loads(content)
            canonical = _canonical_json(data)
            if content != canonical:
                extra.write_text(canonical)
                changed.append(extra)

    return changed

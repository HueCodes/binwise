"""Smoke tests for the binwise dataset and tooling.

These are fast, network-free, deterministic checks. CI runs them on every PR
alongside `binwise validate` and `binwise format --check`. The goal is not
exhaustive coverage but a small set of sentinels that catch the failure modes
that have actually bitten us: schema drift, taxonomy drift, non-canonical JSON
landing on main, and prompt-prefix instability that would silently kill cache
hits.
"""

from __future__ import annotations

import json
from pathlib import Path

from binwise import source_check as sc
from binwise import validate as v
from binwise.agent import _build_system_prompt
from binwise.rules import load_city

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_seed_validation_clean() -> None:
    """The committed dataset validates with zero errors. (Warnings allowed.)"""
    report = v.validate_all()
    assert report.errors == [], "\n".join(f"{i.path}: {i.message}" for i in report.errors)


def test_classify_source_url() -> None:
    """Source URLs are bucketed correctly into gov/hauler/other."""
    assert v._classify_source_url("https://www.seattle.gov/utilities/where-does-it-go") == "gov"
    assert v._classify_source_url("https://sfenvironment.org/recycle") == "gov"  # municipal-dept allowlist
    assert v._classify_source_url("https://example.org/recycle") == "other"
    assert v._classify_source_url("https://www.recology.com/recology-san-francisco/what-goes-where/") == "hauler"
    assert v._classify_source_url("https://www.wm.com/us/en/inside-wm/recycling") == "hauler"
    assert v._classify_source_url("https://medium.com/@somebody/recycling-tips") == "other"
    assert v._classify_source_url("https://example.gov.uk/waste") == "gov"


def test_prompt_determinism() -> None:
    """The system prompt is byte-stable across rebuilds and dict key order.

    This is load-bearing for prompt caching: any byte change in the prefix
    invalidates the cache, so non-determinism here means we silently lose
    every cache hit.
    """
    sf = load_city("san-francisco")
    p1 = _build_system_prompt(sf)
    p2 = _build_system_prompt(sf)
    assert p1 == p2

    shuffled = {k: sf[k] for k in reversed(list(sf.keys()))}
    p3 = _build_system_prompt(shuffled)
    assert p1 == p3, "prompt must be invariant to source-dict key order (sort_keys=True)"


def test_canonical_json_roundtrip() -> None:
    """Every committed JSON file is already in canonical form.

    `binwise format --check` enforces this in CI; this test catches the same
    drift at unit-test level so a bad formatter change is caught locally.
    """
    targets = [
        *sorted(v.CITIES_DIR.rglob("*.json")),
        v.TAXONOMY_PATH,
        v.SCHEMA_PATH,
        v.TAXONOMY_SCHEMA_PATH,
    ]
    drift = []
    for path in targets:
        content = path.read_text()
        canonical = v._canonical_json(json.loads(content))
        if content != canonical:
            drift.append(path.relative_to(REPO_ROOT))
    assert not drift, f"non-canonical JSON: {drift}"


def test_taxonomy_drift() -> None:
    """Every category referenced by a city file exists in taxonomy.json.

    The validator already enforces this, but we want an explicit test so a
    refactor of the validator can't silently disable the check.
    """
    taxonomy = json.loads(v.TAXONOMY_PATH.read_text())
    taxonomy_ids = {c["id"] for c in taxonomy["categories"]}
    assert "rigid_plastic_1_2" in taxonomy_ids, "anchor category missing from taxonomy"

    referenced: set[str] = set()
    for path in sorted(v.CITIES_DIR.rglob("*.json")):
        data = json.loads(path.read_text())
        for rule in data.get("rules", []):
            if cat := rule.get("category"):
                referenced.add(cat)

    missing = referenced - taxonomy_ids
    assert not missing, f"city files reference unknown taxonomy ids: {sorted(missing)}"


def test_source_check_normalization() -> None:
    """Normalized HTML hash ignores boilerplate but reflects real content changes.

    City pages routinely change build IDs and telemetry on every request.
    The source-change workflow needs to ignore that churn and only alarm
    when the actual rule text changes.
    """
    base = """\
<html>
  <head><script>var build='abc123';</script><style>.x{color:red}</style></head>
  <body>
    <nav>menu</nav>
    <main>
      <h1>Recycling rules</h1>
      <p>Plastic bottles go in the blue bin.</p>
    </main>
    <footer>built 2026-05-04T07:32:11Z</footer>
  </body>
</html>
"""
    only_telemetry_changed = base.replace("abc123", "def456").replace("07:32:11Z", "09:14:22Z")
    rule_changed = base.replace("blue bin", "green bin")

    h_base = sc._hash_content(base, "text/html")
    h_telem = sc._hash_content(only_telemetry_changed, "text/html")
    h_rule = sc._hash_content(rule_changed, "text/html")

    assert h_base == h_telem, "hash should be invariant to script/footer noise"
    assert h_base != h_rule, "hash must change when the actual rule text changes"


def test_source_check_json_content() -> None:
    """JSON content hashes verbatim — every byte matters for API responses."""
    a = '{"a":1,"b":2}'
    b = '{"a":1,"b":3}'
    assert sc._hash_content(a, "application/json") != sc._hash_content(b, "application/json")
    assert sc._hash_content(a, "application/json") == sc._hash_content(a + "\n", "application/json")


def test_source_check_drift_detection() -> None:
    """has_drift surfaces changed and http_error states; ignores new and unchanged."""
    diffs = [
        sc.Diff(
            url="u1",
            cities=["a"],
            state="unchanged",
            last_hash="x",
            current_hash="x",
            last_checked="2026-01-01",
            status=200,
            error=None,
        ),
        sc.Diff(
            url="u2",
            cities=["b"],
            state="new",
            last_hash=None,
            current_hash="y",
            last_checked=None,
            status=200,
            error=None,
        ),
    ]
    assert not sc.has_drift(diffs)

    diffs.append(
        sc.Diff(
            url="u3",
            cities=["c"],
            state="changed",
            last_hash="x",
            current_hash="z",
            last_checked="2026-01-01",
            status=200,
            error=None,
        )
    )
    assert sc.has_drift(diffs)

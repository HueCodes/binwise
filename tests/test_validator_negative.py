"""Negative tests for the city-file validator.

`_validate_one` carries roughly a dozen invariants (slug match, country/state
match, bin/category integrity, source URL scheme, archive_url host, date
sanity). The smoke test only exercises the happy path against committed data,
so a refactor that silently dropped one of these checks would still ship a
green CI. These tests pin each error message to a known-bad input.

The dataset under cities/ is the source of truth for "valid"; we copy a real
file into tmp and mutate it minimally per case so that every test isolates a
single invariant.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from binwise import validate as v


def _load_valid_city() -> dict[str, Any]:
    return json.loads((v.CITIES_DIR / "us" / "wa" / "seattle.json").read_text())


def _run(
    tmp_path: Path, city: dict[str, Any], slug: str = "seattle", country: str = "us", state: str = "wa"
) -> v.Report:
    """Write the mutated city to a tmp tree mirroring cities/<country>/<state>/<slug>.json
    and run the validator against it. Uses monkeypatched paths via the standard
    CITIES_DIR-relative layout — the validator derives expected country/state
    from path components, so we have to place the file accordingly."""
    target_dir = tmp_path / country / state
    target_dir.mkdir(parents=True)
    target = target_dir / f"{slug}.json"
    target.write_text(v._canonical_json(city))

    schema = v._load_schema()
    taxonomy = v._load_taxonomy()
    taxonomy_ids = {c["id"] for c in taxonomy["categories"]}

    report = v.Report()
    # Temporarily repoint CITIES_DIR for path.relative_to() to work.
    original = v.CITIES_DIR
    v.CITIES_DIR = tmp_path
    try:
        v._validate_one(target, schema, taxonomy_ids, report)
    finally:
        v.CITIES_DIR = original
    return report


def _error_messages(report: v.Report) -> list[str]:
    return [i.message for i in report.errors]


def test_empty_rules_array_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["rules"] = []
    msgs = _error_messages(_run(tmp_path, city))
    assert any("rules array is empty" in m for m in msgs), msgs


def test_duplicate_bin_id_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["bins"].append(copy.deepcopy(city["bins"][0]))
    msgs = _error_messages(_run(tmp_path, city))
    assert any("duplicated" in m and "bins" in m for m in msgs), msgs


def test_duplicate_category_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["rules"].append(copy.deepcopy(city["rules"][0]))
    msgs = _error_messages(_run(tmp_path, city))
    assert any("duplicated" in m and "category" in m for m in msgs), msgs


def test_slug_mismatch_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["slug"] = "not-seattle"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("slug mismatch" in m for m in msgs), msgs


def test_country_mismatch_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["country"] = "CA"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("country mismatch" in m for m in msgs), msgs


def test_state_mismatch_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["state"] = "OR"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("state mismatch" in m for m in msgs), msgs


def test_rule_bin_not_declared_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["rules"][0]["bin"] = "imaginary"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("not declared in bins" in m for m in msgs), msgs


def test_unknown_category_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["rules"][0]["category"] = "nonexistent_category_xyz"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("not in taxonomy.json" in m for m in msgs), msgs


def test_non_wayback_archive_url_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["rules"][0]["source"]["archive_url"] = "https://example.com/snapshot"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("web.archive.org" in m for m in msgs), msgs


def test_future_last_verified_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["last_verified"] = "2099-01-01"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("future" in m and "last_verified" in m for m in msgs), msgs


def test_future_retrieved_is_an_error(tmp_path: Path) -> None:
    city = _load_valid_city()
    city["rules"][0]["source"]["retrieved"] = "2099-01-01"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("future" in m and "retrieved" in m for m in msgs), msgs


@pytest.mark.parametrize("scheme", ["file://", "ftp://", "javascript:"])
def test_non_http_source_url_is_rejected_by_schema(tmp_path: Path, scheme: str) -> None:
    """The schema's url pattern (^https?://) is the supply-chain guardrail for
    source_check._fetch — without it, a malicious PR could land a file:// URL
    that the daily check-sources cron would happily urlopen."""
    city = _load_valid_city()
    city["rules"][0]["source"]["url"] = f"{scheme}etc/passwd"
    msgs = _error_messages(_run(tmp_path, city))
    assert any("schema:" in m and "rules/0/source/url" in m for m in msgs), msgs

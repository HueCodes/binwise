"""Tests for CLI-side rendering and side-effect contracts.

The pieces tested here are the ones whose failure modes are silent:

- `_render_coverage_section`: builds the README coverage table. If it ever
  drops a city or rejects one (e.g. on a malformed primary_source), the
  README still looks plausible and `coverage --check` passes against the
  (also-wrong) regenerated output. Tests pin "every committed city appears."
- `source_check.check(update=False)`: must not mutate the committed baseline.
  CI scripts depend on this — a side-effecting check would silently rewrite
  `.github/source-hashes.json` on every scheduled run.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from binwise import source_check as sc
from binwise import validate as v
from binwise.cli import _render_coverage_section, _splice_coverage_table


def test_coverage_section_includes_every_committed_city() -> None:
    section = _render_coverage_section()
    cities = [json.loads(p.read_text()) for p in sorted(v.CITIES_DIR.rglob("*.json"))]

    assert f"{len(cities)} cities" in section
    for c in cities:
        assert c["name"] in section, f"city {c['name']!r} missing from rendered coverage table"
        assert f"`{c['verification_level']}`" in section


def test_coverage_section_matches_committed_readme() -> None:
    """The committed README's coverage block equals what the renderer produces.

    `coverage --check` enforces this in CI; this test catches the same drift at
    unit-test level so a refactor of the renderer is caught locally.
    """
    readme = (v.REPO_ROOT / "README.md").read_text()
    rebuilt = _splice_coverage_table(readme, _render_coverage_section())
    assert readme == rebuilt, "committed README coverage block is stale; run `binwise coverage`"


def test_check_sources_is_readonly_without_update(tmp_path: Path, monkeypatch) -> None:
    """A bare `binwise check-sources` must not mutate the committed baseline.

    Previously check() unconditionally rewrote source-hashes.json — refreshing
    last_checked dates and adding "new" entries even when invoked read-only.
    A dev running the check locally ended up with a dirty working tree.
    """
    # Copy the committed baseline to tmp and repoint HASHES_PATH at it. Skip
    # network by stubbing _fetch to a deterministic non-changing response.
    tmp_baseline = tmp_path / "source-hashes.json"
    shutil.copy(sc.HASHES_PATH, tmp_baseline)
    before = tmp_baseline.read_text()

    monkeypatch.setattr(sc, "HASHES_PATH", tmp_baseline)
    monkeypatch.setattr(sc, "_fetch", lambda url: (200, "stubbed-hash-that-does-not-match", "text/html", None))

    sc.check(update=False)
    assert tmp_baseline.read_text() == before, "check(update=False) must not write the baseline"

    sc.check(update=True)
    assert tmp_baseline.read_text() != before, "check(update=True) must write the baseline"

from __future__ import annotations

import json
import sys
from pathlib import Path

CITIES_DIR = Path(__file__).resolve().parents[2] / "cities"


def _slug(s: str) -> str:
    return s.lower().replace(" ", "-")


def list_cities() -> list[dict]:
    out = []
    for path in sorted(CITIES_DIR.rglob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            # A corrupt city file would otherwise vanish from list-cities and
            # from the web demo dropdown with no signal. CI's `binwise validate`
            # catches malformed JSON at the schema layer; this print is the
            # local-dev safety net for the same failure mode.
            print(f"warning: skipping {path.relative_to(CITIES_DIR)}: {e}", file=sys.stderr)
            continue
        out.append(
            {
                "slug": path.stem,
                "city": data.get("name"),
                "state": data.get("state"),
                "country": data.get("country"),
                "qid": data.get("qid"),
                "verification_level": data.get("verification_level"),
                "path": path,
            }
        )
    return out


def load_city(slug: str) -> dict:
    slug = _slug(slug)
    for entry in list_cities():
        if entry["slug"] == slug:
            return json.loads(entry["path"].read_text())
    raise FileNotFoundError(
        f"No ruleset for city '{slug}'. Run `binwise list-cities` to see what's available, "
        f"or add one at cities/<country>/<state>/{slug}.json (see CONTRIBUTING.md)."
    )

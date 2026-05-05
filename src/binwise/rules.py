from __future__ import annotations

import json
from pathlib import Path

CITIES_DIR = Path(__file__).resolve().parents[2] / "cities"


def _slug(s: str) -> str:
    return s.lower().replace(" ", "-")


def list_cities() -> list[dict]:
    out = []
    for path in sorted(CITIES_DIR.rglob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
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

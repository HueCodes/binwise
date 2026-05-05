"""Source-change detection for city primary_source URLs.

Each city file declares a `primary_source` URL — the entry point a re-verifier
starts from. Rules drift when those upstream pages change, but date-based
staleness ("last_verified > 12 months") catches drift only after it's already
old. This module catches it within a day by hashing a normalized signature of
the page content and comparing against a committed baseline at
`.github/source-hashes.json`.

The baseline is hand-curated. CI runs `check()` read-only on a schedule and
opens an issue when drift is detected. The maintainer then either re-verifies
(which updates city files but not the baseline) or — if the upstream change
is cosmetic — runs `binwise check-sources --update` to rebaseline.

Why hash a normalized signature, not the raw bytes:

City pages routinely change build IDs, telemetry payloads, A/B test markers,
and timestamps on every request. Hashing raw HTML alarms on every check.
Stripping scripts, styles, nav/header/footer, and tags before hashing keeps
the signal-to-noise high enough that a true rule change reliably triggers
while routine churn doesn't.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .validate import CITIES_DIR, REPO_ROOT

HASHES_PATH = REPO_ROOT / ".github" / "source-hashes.json"
USER_AGENT = "Mozilla/5.0 (compatible; binwise-source-check/0.1)"
TIMEOUT = 30


@dataclass
class Diff:
    url: str
    cities: list[str]
    state: str  # "unchanged" | "changed" | "new" | "http_error"
    last_hash: str | None
    current_hash: str | None
    last_checked: str | None
    status: int
    error: str | None


def _normalize_html(html: str) -> str:
    h = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    h = re.sub(r"<style[^>]*>.*?</style>", "", h, flags=re.S | re.I)
    for tag in ("nav", "header", "footer"):
        h = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", h, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", text).strip()


def _hash_content(content: str, content_type: str | None) -> str:
    if content_type and "json" in content_type.lower():
        signature = content.strip()
    else:
        signature = _normalize_html(content)
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def _fetch(url: str) -> tuple[int, str | None, str | None, str | None]:
    """Return (status, content_hash, content_type, error)."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ct = resp.headers.get("Content-Type", "")
            return resp.status, _hash_content(body, ct), ct, None
    except HTTPError as e:
        return e.code, None, None, f"HTTP {e.code}: {e.reason}"
    except URLError as e:
        return 0, None, None, f"URL error: {e.reason}"
    except TimeoutError:
        return 0, None, None, "timeout"
    except Exception as e:  # pragma: no cover — defensive
        return 0, None, None, f"{type(e).__name__}: {e}"[:200]


def _collect_primary_sources() -> dict[str, list[str]]:
    by_url: dict[str, list[str]] = {}
    for path in sorted(CITIES_DIR.rglob("*.json")):
        data = json.loads(path.read_text())
        url = data.get("primary_source")
        slug = data.get("slug")
        if url and slug:
            by_url.setdefault(url, []).append(slug)
    return by_url


def _load_baseline() -> dict[str, dict]:
    if not HASHES_PATH.exists():
        return {}
    return json.loads(HASHES_PATH.read_text())


def _save_baseline(baseline: dict[str, dict]) -> None:
    HASHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    HASHES_PATH.write_text(json.dumps(baseline, sort_keys=True, indent=2) + "\n")


def check(update: bool = False) -> list[Diff]:
    by_url = _collect_primary_sources()
    baseline = _load_baseline()
    new_baseline: dict[str, dict] = {}
    diffs: list[Diff] = []
    today = date.today().isoformat()

    for url, slugs in sorted(by_url.items()):
        last = baseline.get(url)
        status, cur_hash, _ct, err = _fetch(url)

        if err is not None:
            state = "http_error"
        elif last is None:
            state = "new"
        elif last.get("hash") == cur_hash:
            state = "unchanged"
        else:
            state = "changed"

        diffs.append(
            Diff(
                url=url,
                cities=sorted(slugs),
                state=state,
                last_hash=(last or {}).get("hash"),
                current_hash=cur_hash,
                last_checked=(last or {}).get("last_checked"),
                status=status,
                error=err,
            )
        )

        # Decide what to write back to the baseline.
        # - new: always record the freshly observed hash (first-seen baseline).
        # - unchanged: refresh last_checked.
        # - changed: only overwrite when --update; otherwise preserve old hash.
        # - http_error: preserve old entry verbatim if it exists.
        if state in ("new", "unchanged"):
            new_baseline[url] = {"hash": cur_hash, "last_checked": today, "cities": sorted(slugs)}
        elif state == "changed":
            if update:
                new_baseline[url] = {"hash": cur_hash, "last_checked": today, "cities": sorted(slugs)}
            elif last is not None:
                new_baseline[url] = last
        elif last is not None:
            new_baseline[url] = last

    # Drop entries for URLs no longer referenced by any city file.
    for url in list(baseline):
        if url not in by_url:
            new_baseline.pop(url, None)

    _save_baseline(new_baseline)
    return diffs


def diffs_to_json(diffs: list[Diff]) -> str:
    return json.dumps([asdict(d) for d in diffs], sort_keys=True, indent=2) + "\n"


def has_drift(diffs: list[Diff]) -> bool:
    return any(d.state in ("changed", "http_error") for d in diffs)


__all__ = ["Diff", "check", "diffs_to_json", "has_drift", "HASHES_PATH"]

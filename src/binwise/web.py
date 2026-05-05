from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import rules as rules_module
from .agent import sort_image

# 10 sorts per hour per IP and a 10 MB upload cap. Public demo guard rails:
# enough to let a curious visitor try the demo and a maintainer-funded API
# key absorb the cost; small enough to make the endpoint a poor target for
# abuse. Both numbers are anchored in SCOPE.md Phase 3.
SORT_RATE_LIMIT = "10/hour"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="binwise",
    description="Point your camera at trash. Get a verdict.",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/cities")
def cities() -> list[dict]:
    return [
        {
            "slug": c["slug"],
            "city": c["city"],
            "state": c["state"],
            "country": c["country"],
            "verification_level": c["verification_level"],
        }
        for c in rules_module.list_cities()
    ]


@app.post("/sort")
@limiter.limit(SORT_RATE_LIMIT)
async def sort(request: Request, image: UploadFile = File(...), city: str = Form(...)) -> dict:
    try:
        rules = rules_module.load_city(city)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    body = await image.read()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    suffix = Path(image.filename or "image.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        result = sort_image(tmp_path, rules)
    finally:
        tmp_path.unlink(missing_ok=True)

    bin_label = {b["id"]: b["label"] for b in rules["bins"]}
    bin_label["unknown"] = "unknown (not covered by city rules)"

    items = [{**item, "bin_label": bin_label.get(item["bin"], item["bin"])} for item in result["items"]]

    return {
        "city": {
            "name": rules["name"],
            "state": rules["state"],
            "country": rules["country"],
            "verification_level": rules.get("verification_level"),
        },
        "items": items,
        "usage": result["usage"],
    }


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>binwise</title>
<style>
  :root {
    --bg: #fafaf7;
    --fg: #1a1a1a;
    --muted: #6b6b6b;
    --line: #e2e2dc;
    --bin-recycling: #2563eb;
    --bin-compost: #16a34a;
    --bin-landfill: #525252;
    --bin-hazardous: #dc2626;
    --bin-special: #7c3aed;
    --bin-unknown: #a3a3a3;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--fg);
    padding: 24px;
    max-width: 720px;
    margin: 0 auto;
    padding-bottom: env(safe-area-inset-bottom, 24px);
  }
  h1 { margin: 0 0 4px; font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }
  .subtitle { color: var(--muted); margin: 0 0 32px; }
  form { display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; }
  label { font-weight: 600; font-size: 14px; }
  select, input[type=file] {
    font-size: 16px; padding: 12px; border: 1px solid var(--line);
    border-radius: 8px; background: white; width: 100%;
  }
  button {
    font: inherit; font-weight: 600; padding: 14px;
    background: var(--fg); color: white; border: 0;
    border-radius: 8px; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: wait; }
  .preview { margin-top: 8px; max-height: 280px; border-radius: 8px; }
  .results { display: flex; flex-direction: column; gap: 12px; }
  .card {
    background: white; border: 1px solid var(--line); border-left-width: 4px;
    border-radius: 8px; padding: 16px;
  }
  .card[data-bin=recycling] { border-left-color: var(--bin-recycling); }
  .card[data-bin=compost]   { border-left-color: var(--bin-compost); }
  .card[data-bin=landfill]  { border-left-color: var(--bin-landfill); }
  .card[data-bin=hazardous] { border-left-color: var(--bin-hazardous); }
  .card[data-bin=special]   { border-left-color: var(--bin-special); }
  .card[data-bin=unknown]   { border-left-color: var(--bin-unknown); }
  .item { font-weight: 600; font-size: 18px; margin-bottom: 4px; }
  .bin { font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 8px; }
  .prep { background: var(--bg); padding: 8px 12px; border-radius: 6px; font-size: 14px; margin-bottom: 8px; }
  .why { color: var(--muted); font-size: 14px; }
  .error { color: var(--bin-hazardous); padding: 12px; background: white; border: 1px solid var(--bin-hazardous); border-radius: 8px; }
  .warn {
    padding: 12px 14px; background: #fffbeb; border: 1px solid #f59e0b;
    border-radius: 8px; font-size: 14px; color: #78350f; margin-bottom: 16px;
  }
  .warn strong { color: #92400e; }
  .footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
  .footer a { color: var(--muted); }
</style>
</head>
<body>
<h1>binwise</h1>
<p class="subtitle">Point your camera at trash. Get a verdict.</p>

<form id="form">
  <div>
    <label for="city">City</label>
    <select id="city" name="city" required></select>
    <div id="city-warn" class="warn" hidden></div>
  </div>
  <div>
    <label for="image">Photo</label>
    <input id="image" name="image" type="file" accept="image/*" capture="environment" required>
    <img id="preview" class="preview" hidden>
  </div>
  <button id="submit" type="submit">Sort</button>
</form>

<div id="results" class="results"></div>

<div class="footer">
  <p style="margin-top:0;">
    binwise output is a guide, not authoritative. Recycling rules change and
    sources go stale. When in doubt, check your hauler's page directly.
    Provided as is, with no warranty.
  </p>
  <p style="margin-bottom:0;">
    Add your city: open a PR with a JSON file at <code>cities/&lt;country&gt;/&lt;state&gt;/&lt;slug&gt;.json</code>.
    See <a href="/docs">/docs</a> for the API.
  </p>
</div>

<script>
const $ = (id) => document.getElementById(id);

const cityIndex = {};

async function loadCities() {
  const res = await fetch('/cities');
  const cities = await res.json();
  const sel = $('city');
  for (const c of cities) {
    cityIndex[c.slug] = c;
    const opt = document.createElement('option');
    opt.value = c.slug;
    const tag = c.verification_level === 'unverified' ? ' (unverified)' : '';
    opt.textContent = c.city + ', ' + c.state + tag;
    sel.appendChild(opt);
  }
  updateCityWarn();
}

function updateCityWarn() {
  const sel = $('city');
  const warn = $('city-warn');
  const c = cityIndex[sel.value];
  if (c && c.verification_level === 'unverified') {
    warn.innerHTML = '<strong>Unverified rules.</strong> ' + escapeHtml(c.city) +
      ' rules have not been line-by-line verified against the city/hauler source. ' +
      'Treat output as best-effort and confirm with your hauler before relying on it.';
    warn.hidden = false;
  } else {
    warn.hidden = true;
  }
}

$('city').addEventListener('change', updateCityWarn);

$('image').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  $('preview').src = url;
  $('preview').hidden = false;
});

$('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const submit = $('submit');
  const results = $('results');
  results.innerHTML = '';
  submit.disabled = true;
  submit.textContent = 'Sorting...';

  const fd = new FormData();
  fd.append('city', $('city').value);
  fd.append('image', $('image').files[0]);

  try {
    const res = await fetch('/sort', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    const data = await res.json();
    if (!data.items.length) {
      results.innerHTML = '<div class="card"><div class="item">No items identified.</div></div>';
      return;
    }
    for (const item of data.items) {
      const card = document.createElement('div');
      card.className = 'card';
      card.dataset.bin = item.bin;
      let html = '<div class="item">' + escapeHtml(item.item) + '</div>';
      html += '<div class="bin">' + escapeHtml(item.bin_label) + '</div>';
      if (item.prep) html += '<div class="prep">' + escapeHtml(item.prep) + '</div>';
      html += '<div class="why">' + escapeHtml(item.why) + '</div>';
      card.innerHTML = html;
      results.appendChild(card);
    }
  } catch (err) {
    const div = document.createElement('div');
    div.className = 'error';
    div.textContent = err.message;
    results.appendChild(div);
  } finally {
    submit.disabled = false;
    submit.textContent = 'Sort';
  }
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

loadCities();
</script>
</body>
</html>
"""

# binwise scope (v0.1 → public launch)

Anchored: 2026-05-02
Target: Show HN-grade public launch with credible adoption path. Iterating in polished, merge-ready chunks. Weeks-to-months timeline.

This document is the source of truth for what's in v0.1 vs. what's deferred. Work that doesn't appear here either fits an existing phase or amends this doc explicitly.

---

## Phase 1 — foundation correctness

Goal: every public claim about the dataset and code is true. No documentation lies, no broken endpoints, no silent data-quality gaps.

- [ ] Fix `web.py:58` `rules["city"]` KeyError → `rules["name"]`
- [ ] Fix stale `rules/` path strings in `cli.py:62` and `web.py:149`
- [ ] Write `schema/taxonomy-v0.1.json`; validate `taxonomy.json` against it in CI
- [ ] Validator additions: taxonomy `id` uniqueness, bin `id` uniqueness on cities, empty-rules error, schema meta-validation, archive_url host check
- [ ] Surface `verification_level: unverified` warning in CLI `sort` output and web demo
- [ ] Add 5 smoke tests: seed validation, source classification, prompt determinism, canonical JSON round-trip, taxonomy drift
- [ ] CI hardening: schema meta-validation, taxonomy validation, ruff, secret scan, multi-Python matrix (3.11, 3.12), `permissions: contents: read`
- [ ] Liability/safety disclaimer in README + CLI startup banner + serve HTML
- [ ] `MAINTAINERS.md` stub (single entry)
- [ ] v0 self-merge escape clause in CONTRIBUTING.md (until ≥2 maintainers exist)
- [ ] `pyproject.toml`: tighten dep ranges, add `[project.optional-dependencies] dev`
- [ ] Suppress >24-month `verification_level=unverified` auto-downgrade error (it's already `unverified`)

## Phase 2 — credibility moves

Goal: dataset earns trust on its own merits before any public push. Quality bar at launch sets the bar forever.

- [ ] **Re-verify SF** against `recology.com/recology-san-francisco/what-goes-where/`. Read line by line. Fix drift. Convert `plastic_film_and_bags` to `depends` (clean grocery bag → store drop-off; soiled → landfill). Add Wayback `archive_url` for every source. Ladder to `verification_level: reviewed`. Record self as reviewer in commit message.
- [ ] **Re-verify Seattle** against `seattle.gov/.../where-does-it-go-`. Same process.
- [ ] Reserve `binwise`, `binwise-rules`, `@binwise` on PyPI and npm with placeholder packages
- [ ] Archive CalRecycle anchor URL via Wayback; mirror the 68-type list to `docs/calrecycle-snapshot-2026-05-02.md` (facts, uncopyrightable, mirror them)
- [ ] README rewrite: drop "pre-v0.1" framing; lead with wedge sentence (RecycleCheck/Earth911 explicitly named); move "dataset is the project" line above the fold
- [ ] `CITATION.cff` for academic uptake
- [ ] `CODE_OF_CONDUCT.md`, `SECURITY.md` (standard OSS hygiene)
- [ ] Fix Wikipedia QID instruction in CONTRIBUTING.md (Tools menu in right sidebar on modern Wikipedia, not left)

## Phase 3 — discovery infrastructure

Goal: make the dataset discoverable and consumable without anyone needing to ask.

- [ ] Auto-generated coverage table in README (CI hook regenerates on merge: city, state, verification_level, last_verified, primary_source)
- [ ] `binwise taxonomy search <term>` command
- [ ] `binwise archive <url>` command (wraps Wayback Save Page Now)
- [ ] Rate limit + size cap on `/sort` endpoint (slowapi 10/hour per IP, 10MB max upload)
- [ ] Source-change detection bot: scheduled workflow that diffs `primary_source` content hash against fresh fetch + Wayback, opens issue when upstream changed (replaces date-only staleness — the sharp design-audit finding)

## Phase 4 — adoption push

Goal: public launch event. Ends with a Show HN post and coordinated distribution.

- [ ] Deploy hosted no-key web demo (Fly.io or Render). Maintainer-funded API key, server-side, per-IP rate limit
- [ ] Draft HN post copy. Title leads with "open dataset," not AI agent. Submit demo URL, not repo
- [ ] Draft partnership signal blog post: "Why I started binwise: RecycleCheck is closed and Earth911 is a locator"
- [ ] Pre-write civic-tech distribution list: r/datasets, r/civictech, r/opendata, r/ZeroWaste, code-for-america Slack #data, CityLab newsletter, MobilityData / Open Knowledge Foundation lists
- [ ] DM 1-3 cosigner candidates with the live demo URL (do, don't gate launch on)
- [ ] **LAUNCH:** Tuesday morning Pacific. HN post + civic-tech distribution + blog post + tweet thread

## Phase 5 — coverage growth (concurrent with Phases 3-4 and continuing post-launch)

Goal: 10 hand-verified cities at or shortly after launch. Each PR is a worked example for the next contributor.

Target list (subject to local-source quality):

- [ ] New York City (Q60) — DSNY
- [ ] Chicago (Q1297) — Streets and Sanitation
- [ ] Los Angeles (Q65) — LA Sanitation
- [ ] Boston (Q100) — Boston ISD
- [ ] Austin (Q16559) — Austin Resource Recovery
- [ ] Portland, OR (Q6106) — Portland Bureau of Planning and Sustainability
- [ ] Atlanta (Q23556) — Department of Public Works
- [ ] Toronto (Q172) — international signal, schema stress-test

## Phase 6 — schema evolution (post-launch, pre-v1.0)

Goal: address the v0.1 deferrals once 10+ cities and real contributor signal exist.

- [ ] `v0.2-draft` branch with multi-hauler schema sketch
- [ ] Per-rule `verification_level` overrides
- [ ] Multi-stream recycling extension (`bin_subtype`)
- [ ] SFH-vs-MFH dual-rule support
- [ ] Rejected-source domains deny-list (auto-error on `medium.com`, `reddit.com`, etc.)
- [ ] Safety-critical 48-hour dispute SLA + auto-labeling for `battery_lithium`/`household_chemical` etc. routed to compost/recycling
- [ ] Per-source `verification_steps` array (OpenAddresses pattern)
- [ ] File-maintainer opt-in checkbox in PR template

---

## Deferred indefinitely (out of scope for v1.x)

These are real ideas. Not doing them. Listed here so we don't relitigate.

- **IPFS / dat / git-lfs distribution** — overkill at this scale; GitHub + Pages serves
- **HTTP API with CDN** — Pages stable URLs handle the consumption pattern at zero ops cost
- **Dated Anthropic model ID pinning** — bare alias is canonical per current Anthropic docs
- **Switch from `output_config` to tool-use** — `output_config` is the canonical structured-output parameter
- **Mobile contribution app** — over-engineered for v1; GitHub web edits work
- **"Guided contribution web form"** — premature; build when contributor friction is observed
- **Trademark filing** — CC0 dataset doesn't need it pre-launch
- **Real-time city feed integration** — RecycleCheck's wedge; the source-change bot in Phase 3 is the open substitute
- **PyPI/npm package implementations beyond name-reservation** — v1.1 work, not v1.0
- **Earth911-style drop-off location catalog** — explicit non-goal per DESIGN.md §1

---

## Process discipline

- Each phase ships in ordered chunks. Each chunk is mergeable on its own.
- No half-done work in `main`. PRs land green or don't land.
- Phase N starts when Phase N-1 is complete, except: Phase 5 is concurrent with Phases 3-4; Phase 6 starts post-launch.
- Public launch happens at the end of Phase 4. Before that, the repo is public-but-quiet (no announcements).
- Any new work proposed mid-phase either fits an existing chunk or amends this doc.

## Decisions of record

Track major decisions as they're made (schema changes, scope adjustments, audit responses).

- **2026-05-02:** Anchored scope. Target: Show HN-grade launch. License: CC0/MIT. Scope: US-only at v1, international PRs welcome but expect schema iteration.
- **2026-05-02:** Two seed-city audits surfaced 30 findings; categorized into Phases 1-6 above. Two findings rejected as based on stale Anthropic API knowledge (model ID pinning, `output_config` deprecation).

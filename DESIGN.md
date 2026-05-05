# binwise — Design

Status: draft v0.1 (post-review-pass)
Last updated: 2026-05-02

This document captures the load-bearing decisions for binwise, an open dataset of municipal recycling rules. Every future PR gets measured against this doc. Decisions are stated with their tradeoffs so that future contributors understand *why* and not only *what*.

---

## 1. Goals and non-goals

### Goals

- A canonical, machine-readable, per-jurisdiction dataset of recycling rules: which materials go in which bin, in what condition, with what prep, citing the source the rule came from.
- Consumable by other applications without scraping. A consumer app should be able to ask: *given the user's city and an identified item, where does it go and why?* and get a structured answer with a citable source.
- Permissively licensed (CC0 for the data) so that adoption isn't blocked by legal review.
- Community-contributable, with hard quality gates enforced by CI rather than by the maintainer's vigilance.
- Schema-versioned so consumers can pin against a stable contract.

### Non-goals

- **Not a recycling locator.** We do not catalog drop-off points. Earth911 already does that and they do it well. We cite drop-off rules ("batteries → drop-off") but not addresses.
- **Not a collection-schedule database.** When pickup happens is out of scope. `mampfes/hacs_waste_collection_schedule` covers schedules; we link out to it where useful.
- **Not a consumer-product database.** Mapping a barcode to a material is downstream of binwise. A consumer app sits on top of GS1 + binwise; we don't bake GS1 in.
- **Not a regulatory reference.** The EU European List of Waste codes are designed for waste-stream regulatory reporting, not consumer routing. We accept them as cross-reference fields but do not adopt them as the primary taxonomy.

---

## 2. Prior art and the gap

The research pass (see also internal research brief, 2026-05-02) confirmed that no open, forkable, machine-readable dataset of per-jurisdiction recycling rules exists today. The closest comparable efforts:

- **The Recycling Partnership / RecycleCheck** — 9000+ communities, partnership-only, integrates with Consumer Brands Association SmartLabel via QR codes. Closed. The most direct competitor; its closure is the wedge.
- **Earth911** — locator-shaped, commercial API, ToS forbids redistribution.
- **Wikidata** — has `recycling` and `recycling_code` items but no per-city rule modeling.
- **City open-data portals** — publish bin locations, tonnage, schedules, service-area polygons. They do not publish the rule corpus itself. Rules live in HTML pages and PDFs.
- **GitHub** — no comparable dataset. `mampfes/hacs_waste_collection_schedule` is adjacent (schedules, not rules) and is the strongest precedent for the adapter-style federation we adopt.

Therefore: the gap is real and the reason for binwise's existence.

---

## 3. Schema

### Per-jurisdiction file

One JSON file per jurisdiction, at `cities/<country>/<state>/<slug>.json`. (`cities/` rather than `rules/` because each file describes a jurisdiction; the rules are content.)

Top-level shape:

```json
{
  "spec_version": "0.1",
  "qid": "Q62",
  "slug": "san-francisco",
  "name": "San Francisco",
  "country": "US",
  "state": "CA",
  "last_verified": "2026-05-02",
  "verification_level": "reviewed",
  "primary_source": "https://www.recology.com/recology-san-francisco/what-goes-where/",
  "notes": "Recology runs a 3-stream system. Compost is curbside and accepts food-soiled paper.",
  "bins": [
    {"id": "recycling", "label": "blue bin (recycling)", "color": "blue"},
    {"id": "compost",   "label": "green bin (compost)",  "color": "green"},
    {"id": "landfill",  "label": "black bin (landfill)", "color": "black"},
    {"id": "hazardous", "label": "household hazardous waste drop-off"},
    {"id": "special",   "label": "special-handling drop-off"}
  ],
  "rules": [...],
  "edge_cases": [...]
}
```

Why these top-level fields:

- **`spec_version`** — a consumer can pin against a schema version. GTFS's hard-won lesson: a dataset without a spec version becomes unparseable when the schema evolves. Required from v0.1.
- **`qid`** — Wikidata QID is the canonical, ambiguity-free identifier. `Q62` is uniquely San Francisco. Solves Portland-OR (`Q6106`) vs. Portland-ME (`Q187926`) forever, and works for non-city jurisdictions (counties, regions) when we eventually cover them.
- **`slug`** — human-readable label. Must match the file's directory name. Validated in CI.
- **`primary_source`** — the URL a re-verifier should start from when checking the whole file. Not redundant with per-rule `source.url`; the per-rule URLs are where the *specific rule* came from (often the same as `primary_source`, sometimes a hauler PDF or a different sub-page). Think of `primary_source` as the file's entry point, per-rule sources as receipts.
- **`last_verified`** — date a human last read every rule in the file against its source and confirmed the rules match. Distinct from per-rule `source.retrieved` (which is when *that URL* was fetched, possibly months earlier). CI bot flags any file >12 months unverified, auto-downgrades `verification_level` after 24 months.
- **`verification_level`** — see §6. File-level only at v1; per-rule override is a v0.2 candidate.

### Rules

A rule routes a material category to a bin, optionally with conditions:

```json
{
  "category": "rigid_plastic_1_5",
  "bin": "recycling",
  "prep": "rinse, replace caps, leave labels on",
  "rejected_examples": ["plastic bags", "plastic film", "styrofoam"],
  "source": {
    "url": "https://www.recology.com/recology-san-francisco/what-goes-where/",
    "retrieved": "2026-05-02",
    "publisher": "Recology",
    "source_license": "proprietary",
    "archive_url": "https://web.archive.org/web/2026*/https://www.recology.com/recology-san-francisco/what-goes-where/"
  }
}
```

`archive_url` is optional but strongly encouraged — city pages get reorganized, broken links rot the dataset's audit trail. An archive.org snapshot URL preserves the source-as-of-`retrieved` independent of upstream changes.

Conditional rules:

```json
{
  "category": "pizza_box",
  "bin": "depends",
  "conditions": [
    {
      "if": "clean (no grease, no cheese)",
      "then_bin": "recycling",
      "prep": "tear off and recycle clean parts",
      "source": {...}
    },
    {
      "if": "soiled (grease, cheese, food residue)",
      "then_bin": "compost",
      "prep": "tear into pieces",
      "source": {...}
    }
  ]
}
```

### Edge cases

Items that look like one category but are routed differently in this jurisdiction. The agent uses these to override naive identification.

```json
{
  "item": "paper coffee cup",
  "bin": "landfill",
  "why": "plastic-lined; not recyclable in SF and not accepted in compost",
  "source": {...}
}
```

### Schema-shape decisions and their tradeoffs

- **Per-rule provenance, not per-file.** Each rule and each conditional carries its own `source` block with `url`, `retrieved`, `publisher`, `source_license`, optional `archive_url`. This is Wikidata's claim+reference pattern. The cost is verbosity; the benefit is that cities don't update their pages atomically — they update specific rules — and a per-rule provenance model lets us track which rules were verified when, and lets a contributor challenge one rule with a counter-source without invalidating the rest of the file.
- **Closed enum for bin IDs.** `recycling | compost | landfill | hazardous | special | depends` (the last only on `bin`, never on `then_bin`). Bin colors and local labels go in the per-file `bins` array. This separates *routing* (a small fixed vocabulary) from *display* (local color). OSM's lesson: free-text in routing fields fragments the dataset within 50 contributors. Cities that genuinely need more streams (multi-stream recycling, separate organics-vs-yard) are flagged in §11 as a v0.2 schema-extension candidate; v1 maps them onto the closed enum and notes the lossy conflation in `notes`.
- **Free-text `notes` and `prep`, controlled-vocab `category`.** `prep` is human-facing instruction text that varies per city; controlling it is wasted effort. `category` is the join key between cities — it must be controlled. See §4.
- **Free-text `if` conditions in conditional rules.** The `if` field is natural-language (`"clean (no grease, no cheese)"`). The reference consumer is a vision LLM that reads the condition and judges from an image; a static-lookup consumer should treat `bin: "depends"` as "requires evaluation" and surface every condition to the user. We deliberately do *not* invent a mini-DSL here — the cost (parser, ontology) outweighs the value when the dominant consumer is an LLM anyway.
- **Canonical JSON serialization.** Files are stored with sorted keys, two-space indent, LF line endings, and a trailing newline. Enforced in CI via a `binwise format` step that fails the build on diff. Reason: the agent's system prompt is built from the file contents; for the prompt cache to actually hit, the rendered bytes must be deterministic. This also makes diffs reviewable — reordering keys is invisible churn.

---

## 4. Material taxonomy

A controlled vocabulary in `taxonomy.json` at the repo root. Every `category` field in every city file must reference an `id` from `taxonomy.json`. CI rejects unrecognized categories.

The vocabulary anchors on **CalRecycle's Material Type list** (`https://www2.calrecycle.ca.gov/WasteCharacterization/MaterialType`), 68 material types in 10 categories, government-published, stable across study revisions. CalRecycle's facts are not copyrightable (Feist v. Rural Telephone, 499 U.S. 340). A verbatim mirror of the list, dated, lives at `docs/calrecycle-snapshot-2026-05-04.md` so the taxonomy has a citable anchor independent of upstream availability.

`taxonomy.json` shape:

```json
{
  "spec_version": "0.1",
  "derived_from": "CalRecycle Material Type list",
  "categories": [
    {
      "id": "rigid_plastic_1_5",
      "name": "Rigid plastic containers, resin codes #1-#5",
      "calrecycle_type": "Other Plastic Containers",
      "aliases": ["#1", "#2", "#3", "#4", "#5", "PET", "HDPE", "PVC", "LDPE", "PP", "polyethylene terephthalate"],
      "examples": ["water bottle", "milk jug", "yogurt cup"],
      "low_code": "15 01 02"
    }
  ]
}
```

`aliases` exist so that the agent and the validator can normalize free-form identification ("PET cup", "#1 plastic") to a canonical category ID. `low_code` and similar fields (RCRA, GS1) are optional cross-references for downstream interop. We do not adopt EU LoW codes as the primary taxonomy because they're designed for regulatory tonnage reporting and are too granular for consumer routing.

The taxonomy is itself a contributed artifact. New cities introduce new categories; PRs add to `taxonomy.json` and the city file in the same PR (so reviewers see why the new category is needed), but the taxonomy diff is reviewed first by the merge-gate logic — taxonomy changes need two reviewers (see §6) regardless of how trivial the city-file change is. This forces the controlled-vocabulary debate to happen explicitly rather than getting smuggled into a city PR.

To distinguish the two artifacts: the **JSON Schema** (in `schema/v0.1.json`) defines the *shape* a city file must conform to; the **taxonomy** (in `taxonomy.json`) defines the *vocabulary* a city file must draw from for the `category` field. Both are versioned via `spec_version`. Both are published at stable URIs under GitHub Pages.

We considered and rejected:

- **SWICS** — does not exist as a coding system. The acronym surfaces only for the Solid Waste Industry for Climate Solutions methane methodology group.
- **EPA RCRA** — hazardous-waste-only. We use it as a cross-reference for hazardous edge cases.
- **WRAP (UK)** — useful for international expansion; reference only at v1.
- **GS1** — product-side, not waste-side. Out of scope.
- **Free text** — would fragment within 50 cities. OSM's tag-proliferation failure mode is real and observable.

---

## 5. Identifiers

- **Jurisdiction key**: Wikidata QID. SF = `Q62`, Seattle = `Q5083`, NYC = `Q60`. Stable across name changes, languages, and disambiguation.
- **File path**: `cities/<country-iso2>/<state-or-province-code>/<slug>.json`. Slug is human-readable, lowercase, hyphenated, must match the file's `slug` field, validated in CI.
- **"City" defined**: the smallest jurisdiction that publishes its own recycling rules. Defaults to municipality. Counties (e.g. unincorporated King County) and states (rare) get their own files when they have their own rule corpus. NYC's DSNY-published rules sit at the city level (`Q60`), not borough level.

---

## 6. Provenance and verification

### Per-rule source block

Required fields:

| Field           | Type    | Description                                                              |
|-----------------|---------|--------------------------------------------------------------------------|
| `url`           | string  | Source URL the rule was derived from                                     |
| `retrieved`     | date    | When the URL was last accessed                                           |
| `publisher`     | string  | Who published it: city name, hauler name, or agency                      |
| `source_license`| enum    | `cc0` \| `cc_by` \| `cc_by_sa` \| `proprietary` \| `unknown` (page license; the *fact itself* is always CC0 under Feist v. Rural) |
| `archive_url`   | string  | Optional Wayback Machine URL for the page as of `retrieved`. Strongly encouraged — preserves the audit trail when upstream pages move or 404. |

`source_license` documents the source page's licensing for transparency. The *fact itself* is always CC0 in our dataset (Feist), regardless of `source_license`. We never reproduce source prose verbatim — rules are normalized into the schema.

### Verification levels

A jurisdiction file carries a single `verification_level`. Per-rule overrides are deferred to v0.2 — at v1, the file's level is the level of every rule in it. This avoids ambiguity at the cost of granularity (a single questionable rule downgrades the whole file's badge until corrected, which is the right pressure).

- **`unverified`** — extracted by an LLM or a contributor without source-checking. Hidden from default consumer queries; visible only with `--include-unverified`. New PRs can land at this level for community follow-up; the maintainer ladders them up after review.
- **`reviewed`** — a human has read every rule in the file against its sources and confirmed they match. Reviewer GitHub handle recorded in the merge commit. CI requires at least one reviewer for `.gov` and known-hauler sources, two for any other published source, and rejects blog/forum/Reddit/AI-summary sources outright.
- **`resident_confirmed`** — `reviewed` plus a contributor who lives in the jurisdiction has signed off. Top tier. Surfaces in CLI and web output as a badge.

CI categorizes each rule's `source.url` automatically (`.gov` / known hauler domain via an allowlist in the repo / other) to determine the reviewer threshold. This is encoded in the validator rather than relying on contributors to self-classify, because contributors will under-classify their own sources.

**Taxonomy changes are reviewed separately and more strictly.** Any PR that modifies `taxonomy.json` (adding a category, changing an alias, modifying a cross-reference) requires two reviewers regardless of source authority — taxonomy changes affect every consumer of the dataset, so the review bar is higher than for a single city file.

### Re-verification cadence

A file's `last_verified` date drives a CI bot that runs nightly:

- **>12 months unverified** — surfaced as a yellow "stale" badge on the file's coverage entry; an issue is auto-opened tagging the file's maintainer (latest committer) requesting re-verification.
- **>24 months unverified** — `verification_level` auto-downgrades to `unverified` until a re-verification PR lands. The auto-downgrade is reversible only by a re-verification PR, not by hand-editing the field.

Cities change rules, especially after contract renegotiations or state regulation changes. Staleness without surfacing it is the worst failure mode — users trust the dataset, the dataset is wrong, the trust is broken. Surfacing staleness aggressively is the v1 substitute for the real-time city feeds that RecycleCheck has.

### Coverage badge

The README badge shows: total cities, breakdown by `verification_level` (`resident_confirmed` / `reviewed` / `unverified`), count of stale files (>12 months), generated nightly from the same CI bot. Goal is for "resident_confirmed" to grow over time without the project having to ship live data feeds.

### Disputes

The dispute process is simple: file an issue with a counter-source URL. **No counter-source means no dispute** — issues without source citations are closed. This rule is what keeps debates productive.

Severity dictates timeline:

- **Typo or formatting** — file maintainer or any maintainer can fix directly, no waiting period.
- **Substantive rule change** with a clear authoritative counter-source — file maintainer responds. If unanswered for 4 weeks, top-level maintainer adjudicates. Decision recorded in the issue, not just in the merge commit.
- **Conflicting authoritative sources** (e.g. city page says X, hauler page says Y) — both cited in the file's `notes`, the rule defaults to the city page, and the discrepancy is logged as an open issue with the `conflicting-sources` label until the contributor confirms with the hauler directly.

---

## 7. Versioning

Two distinct version numbers:

- **`spec_version`** (in each file and in `taxonomy.json`) — declares which schema version this file conforms to. Increments on schema changes. Major for breaking, minor for additive.
- **Dataset version** — semver tags on the repo (`v0.1.0`, `v0.2.0`, ...). Increments when we cut a release. Breaking schema change = major version bump on the dataset, even if the schema only added one optional field, because consumers will need to update.

Schema is published as a JSON Schema document at a stable URI on GitHub Pages: `https://<org>.github.io/binwise/schema/v0.1.json`. Other tools can validate against our schema without depending on our code. GTFS, GeoJSON, and OpenAPI all do this; it's what turns a project's schema into a standard.

---

## 8. Distribution

v1 (now → first stable release):

- **Source of truth**: GitHub repository. PRs against `main`. CI runs JSON-schema validation, taxonomy enforcement, link-checker, slug/QID consistency, source-URL classification.
- **Consumer artifact**: tagged GitHub releases with tarballs of the validated corpus. Stable per-city URLs via GitHub Pages: `https://<org>.github.io/binwise/v0.1/cities/us/ca/san-francisco.json`.

v1.1 (post first stable release):

- **Language packages**: `pip install binwise-rules`, `npm install @binwise/rules`. Auto-published from `main` on tag via GitHub Actions. Each package is a thin wrapper that bundles the latest validated dataset and exposes a typed lookup function.

Deferred:

- HTTP API with CDN caching. Premature for a small dataset. GitHub Pages with stable URLs covers 90% of the consumption pattern at zero ops cost.

---

## 9. License

- **Data**: CC0 1.0 Universal (public domain dedication). Maximizes adoption — companies pull it without legal review. Matches OpenAddresses' index license and Wikidata.
- **Code**: MIT.
- **Per-source `source_license`**: a metadata field on each rule's `source` block, documenting the license of the page the rule was derived from. The fact itself is CC0 regardless (Feist v. Rural). The field exists for transparency, not for IP control.
- **Rejected**: ODbL (share-alike scares off commercial integrators; the explicit goal is consumption by other apps), CC-BY (attribution requirement adds friction without meaningful benefit when the dataset is fact-based and downstream apps would cite anyway).

Disclaimer: contributors are not lawyers and the project carries no indemnity. This mirrors OpenAddresses' precedent — they have aggregated government-published data for over a decade and have not been successfully challenged. We adopt the same posture.

---

## 10. Governance

v0 governance is a single maintainer (project owner). Governance grows as the dataset grows.

**Maintainer responsibilities**:

- Review and merge PRs
- Adjudicate disputes when the file maintainer is unresponsive
- Maintain `taxonomy.json` and the schema
- Cut releases

**File maintainers** (emergent): the latest committer of a city file is its de facto maintainer for dispute response. PRs to a city file ping the file's maintainer first.

**Adding maintainers**: by invitation from the current maintainer set, after demonstrated contribution (typically 3+ merged PRs across multiple cities, or significant taxonomy/tooling work).

**Conflict-of-interest disclosure**: contributors employed by haulers, recycling industry trade groups, or municipal solid-waste departments must disclose in their PR description. This does not disqualify them — they often have the most accurate knowledge — but it is recorded for transparency.

**Public-sources-only rule for industry contributors.** Disclosure isn't enough. Industry-employed contributors must source rules from public documents only — published city or hauler pages, customer-facing PDFs, public press releases. Internal training material, unreleased policy drafts, and non-public communications are out of bounds even when accurate, for two reasons: (1) the project's audit trail must be replicable by any reader, which non-public sources break, and (2) the contributor's employer's IP and confidentiality obligations are theirs to honor, not ours to navigate.

---

## 11. Open questions and v1 deferrals

These are real concerns that we are explicitly punting on for v1. Documented here so we don't pretend they don't exist.

- **Heterogeneous-hauler cities.** Some cities (Houston is the canonical example) have different waste haulers in different neighborhoods, with materially different rules. v1 documents the dominant hauler and notes the gap in the file's `notes` field. Multi-hauler cities get a follow-up schema extension when the cases pile up.
- **Single-family vs. multi-family rules.** Often differ — apartment buildings frequently have constrained sorting compared to SFH. v1 documents SFH rules; multi-family flagged in `notes`. Schema extension for this is a probable v0.2.
- **Multi-stream recycling cities.** Some cities (parts of New England, some EU systems) collect paper separate from glass-and-metal-and-plastic, or have separate organics-vs-yard streams. v1's closed bin enum maps these onto `recycling`/`compost` with the local distinction recorded in the per-bin `label`. Lossy. v0.2 schema extension candidate: a `bin_subtype` field that preserves stream identity.
- **Per-rule `verification_level` overrides.** v1 has file-level only. The case for per-rule: a single dubious edge case shouldn't downgrade the file's badge. The case against: file-level pressure forces every rule to actually get reviewed. Defer to v0.2 if the cost shows up in practice.
- **Special collection days.** Christmas trees, bulky items, hazardous-waste collection events. Out of scope. We link to schedule projects (`mampfes/hacs_waste_collection_schedule`) from `notes` when relevant.
- **Drop-off location lists.** A rule that says "batteries → drop-off" needs a "where?" answer. Earth911 already does this. We name the bin (`special`) and the prep ("drop-off only — see your city's hazardous waste page"); we don't catalog locations.
- **Internationalization.** Schema is designed not to bake in US-specific assumptions (no required `state`, country code on every file, QID as the canonical key), but v1 ships US-only. Non-US PRs welcome but expect schema iteration.
- **Real-time updates.** RecycleCheck integrates with city feeds for live updates. Out of scope at v1; manual re-verification cadence + 12-month staleness flagging is the v1 substitute.

---

## 12. Influences

This design borrows directly from:

- **OpenAddresses** — federated per-jurisdiction files, per-source license metadata, "use at your own risk" disclaimer.
- **Wikidata** — claim+reference provenance, QID-keyed identifiers, fact-derivation discipline.
- **GTFS** — `spec_version` from day one, deliberately boring schema, JSON Schema published at stable URI.
- **public-apis** — strict CI gates, machine-validated PRs, alphabetical ordering.
- **Mozilla Common Voice** — tiered review based on source authority.
- **CalRecycle Material Type list** — the controlled vocabulary anchor.
- **`mampfes/hacs_waste_collection_schedule`** — adapter-style federation, source-URL discipline.

Influence is acknowledged in the project README and CONTRIBUTING; design choices that depart from these precedents are noted inline in this doc.

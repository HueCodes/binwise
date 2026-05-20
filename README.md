# binwise

**Open dataset of municipal recycling rules. The dataset is the project; a reference photo agent is the demo that makes it legible.**

Per-jurisdiction JSON files, schema-validated, every rule cites a source URL. CC0. Three seed cities at `verification_level: reviewed`, US-only at v0.1.

```
cities/us/ca/san-francisco.json
cities/us/ny/new-york-city.json
cities/us/wa/seattle.json
```

---

## Why this exists

The Recycling Partnership's **RecycleCheck** (9000+ communities, integrates with the Consumer Brands Association's SmartLabel via QR codes) is the closest comparable dataset, and it is partnership-only and not redistributable. **Earth911** is locator-shaped: it catalogs drop-off points, not the rule corpus, and its ToS forbids redistribution. **Wikidata** has `recycling` and `recycling_code` items but no per-city rule modeling. **City open-data portals** publish bin locations, schedules, and tonnage — never the rule corpus itself, which lives in HTML pages and PDFs that nobody has structured.

There is no open, forkable, machine-readable dataset of per-jurisdiction recycling rules. binwise fills that gap.

The rules vary in subtle but consequential ways: a yogurt cup is recyclable in Seattle, conditional in SF, trash in much of NJ. Seattle accepts plastic-lined paper coffee cups in recycling when clean and dry; SF accepts B.P.I. certified compostable bags in compost while routing other compostable plastics to landfill. Apps that route a photo to a bin need this corpus.

## Coverage

<!-- COVERAGE-TABLE:START -->
3 cities — 3 reviewed.

| City | Country / State | Verification | Last verified | Source |
|---|---|---|---|---|
| San Francisco | US / CA | `reviewed` | 2026-05-04 | [recology.com](https://www.recology.com/recology-san-francisco/what-goes-where/) |
| New York City | US / NY | `reviewed` | 2026-05-04 | [nyc.gov](https://www.nyc.gov/site/dsny/collection/get-rid-of.page) |
| Seattle | US / WA | `reviewed` | 2026-05-19 | [seattle.gov](https://www.seattle.gov/utilities/your-services/collection-and-disposal/where-does-it-go) |
<!-- COVERAGE-TABLE:END -->

## Disclaimer

binwise is a community dataset, not a guarantee. Recycling rules change, sources go stale, and reasonable people interpret a photo differently. Use the dataset and the reference agent as a *guide*, not as the authoritative source for what your city accepts. When in doubt, check your hauler's page directly. The project is provided **as is, with no warranty** (see [LICENSE-DATA](LICENSE-DATA) and [LICENSE-CODE](LICENSE-CODE)). Contributors carry no liability.

City files marked `verification_level: unverified` have not been line-by-line verified against the source. The CLI and web demo surface this status in their output.

## Use the dataset

The data lives under `cities/<country>/<state>/<slug>.json`. Schema in `schema/v0.1.json`. Material taxonomy in `taxonomy.json` (anchored on the [CalRecycle Material Type list](docs/calrecycle-snapshot-2026-05-04.md), mirrored locally for stability).

Read `cities/us/ca/san-francisco.json` to see the shape. Every rule has a `category` (referencing `taxonomy.json`), a `bin` (one of `recycling`, `compost`, `landfill`, `hazardous`, `special`, or `depends` for conditional rules), `prep` instructions, and a `source` block citing the URL it came from with a `retrieved` date and `source_license`.

If you're building a recycling app: clone the repo or fetch a tagged release tarball. The schema is documented in [DESIGN.md](DESIGN.md) and stable within the `0.x` series.

## Contribute a city

Adding your city is the highest-leverage contribution. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full process. The short version:

1. Find your city's authoritative recycling page (city `.gov` or hauler).
2. Find your Wikidata QID.
3. Copy a template: `cp cities/us/ca/san-francisco.json cities/<country>/<state>/<your-slug>.json`.
4. Fill it in, citing the source on every rule.
5. Run `binwise validate` and `binwise format` locally.
6. Open a PR.

Three cities ship as worked examples. Quality bar at launch sets the bar forever; we'd rather have 10 great cities than 100 sloppy ones.

## Run the demo

The reference implementation: a vision LLM agent that takes a photo + a city slug and returns a structured verdict.

```sh
git clone <repo>
cd binwise
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
export ANTHROPIC_API_KEY=...

binwise list-cities
binwise sort path/to/photo.jpg --city san-francisco --show-usage
binwise serve --host 0.0.0.0   # phone-camera demo at http://<your-ip>:8000
```

The agent ingests the city's rules JSON as its system prompt (prompt-cached for efficiency), receives the photo, and returns one verdict per identified item with bin, prep, and a one-line citation of the rule that applies.

## Dataset tooling

```sh
binwise validate                # schema + taxonomy + bin-id consistency + slug/path/staleness checks
binwise format                  # rewrite files in canonical JSON form
binwise format --check          # exit nonzero if anything would change (CI uses this)
binwise list-cities             # what's currently in the dataset
binwise taxonomy search <term>  # find an existing taxonomy category by id, name, alias, or example
binwise coverage                # regenerate the coverage table region in this README
binwise archive <url>           # save a URL to the Wayback Machine, print the dated snapshot URL
binwise check-sources           # diff each city's primary_source against the committed baseline
binwise check-sources --update  # accept current page hashes as the new baseline
```

CI runs `validate`, `format --check`, and `coverage --check` on every PR. A scheduled workflow runs `check-sources` daily and opens a GitHub issue when an upstream source diverges from the committed baseline.

## Design

[DESIGN.md](DESIGN.md) is the load-bearing document. It captures the schema, identifier scheme, provenance model, taxonomy choice, license, governance, and v1 deferrals — with the tradeoffs spelled out so future contributors understand why.

Skim DESIGN.md before opening a non-trivial PR.

## License

- **Data** (everything under `cities/`, `taxonomy.json`, `schema/`, `docs/calrecycle-snapshot-*.md`): CC0 1.0 — see [LICENSE-DATA](LICENSE-DATA).
- **Code** (the `binwise` Python package): MIT — see [LICENSE-CODE](LICENSE-CODE).

The `source_license` field on each rule documents the *source page* it was derived from (usually `proprietary`). The fact itself is always CC0; that field is informational. Facts are not copyrightable under US law (Feist v. Rural Telephone, 499 U.S. 340).

## Acknowledgements

This project takes its design choices from:
[OpenAddresses](https://github.com/openaddresses/openaddresses) (federation + per-source license),
[Wikidata](https://wikidata.org) (claim+reference provenance, QID-keyed identifiers),
[GTFS](https://gtfs.org) (`spec_version` from day one),
[public-apis](https://github.com/public-apis/public-apis) (CI gates),
[Mozilla Common Voice](https://commonvoice.mozilla.org) (tiered review),
the [CalRecycle Material Type list](https://www2.calrecycle.ca.gov/WasteCharacterization/MaterialType) (controlled vocabulary anchor),
and [`mampfes/hacs_waste_collection_schedule`](https://github.com/mampfes/hacs_waste_collection_schedule) (adapter-style federation).

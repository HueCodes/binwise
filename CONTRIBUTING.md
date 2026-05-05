# Contributing to binwise

binwise is an open dataset of municipal recycling rules. The dataset is the project — code is just what we use to consume and validate it. The most valuable contribution is **adding your city**.

This doc covers the rules. The full design is in [DESIGN.md](DESIGN.md).

---

## Quick rules (the bar)

Every PR must pass these. CI enforces most of them; the rest the maintainer enforces in review.

1. **Cite a public source.** Every rule has a `source.url` pointing to the city or hauler page it came from. No URL, no merge.
2. **Don't paraphrase from memory.** Read the actual page. PRs sourced from "I think this is how my city does it" get rejected.
3. **One PR per change of intent.** Adding a new city is one PR. Adding a category to the taxonomy is a separate PR (or bundled with the city PR that needs it). Renaming categories is its own PR.
4. **No emojis.** Anywhere — not in commit messages, not in PR descriptions, not in city `notes`.
5. **PR descriptions are terse.** A few sentences max. State what the PR does and the source you used. Don't repeat what the diff already shows.
6. **Run validation locally before pushing**: `binwise validate` and `binwise format --check`. CI will reject otherwise.
7. **Don't take public/external actions on behalf of the project** without maintainer approval. No commenting on other cities' issues unless you're the maintainer of that city's file.

---

## Adding a city

The process. Estimate: a careful first city takes about an hour because you're learning; subsequent ones drop to 20 minutes.

### 1. Find your authoritative source

Search `<your city> what goes in recycling` (or "where does it go"). Land on either:

- The city's `.gov` page (preferred), OR
- The official hauler's page (Recology, Waste Management, Republic Services, etc., depending on your area).

**Reject** as sources: blog posts, Reddit, ChatGPT-style summaries, third-party recycling apps, news articles. These are not authoritative even when they're correct.

If your city has both a `.gov` page and a hauler page, and they disagree, cite both — the city page in `primary_source`, the hauler in the rule-level `source.url` for the disputed rule, and add a `notes` block explaining the discrepancy. See DESIGN.md §6 for the dispute process.

### 2. Find your Wikidata QID

Open Wikipedia for your city. On modern Wikipedia (Vector 2022 skin), the Wikidata item link is under **Tools** in the right-hand sidebar; on older skins it's in the left sidebar. The QID is the page identifier on Wikidata, e.g. `Q62` for San Francisco, `Q5083` for Seattle. Put this in the file's `qid` field.

### 3. Copy a template

```sh
cp cities/us/ca/san-francisco.json cities/<country>/<state>/<your-slug>.json
```

Pick whichever existing city has the closest bin structure to yours.

### 4. Fill in the file

Walk through the file top-to-bottom:

- `qid` — your Wikidata QID
- `slug` — must match the filename (without `.json`)
- `name`, `country`, `state` — straightforward
- `last_verified` — today's date, ISO format (`YYYY-MM-DD`)
- `verification_level` — start at `unverified`. Set to `reviewed` only after you've matched every rule against the source URL. Set to `resident_confirmed` only if you live in this jurisdiction.
- `primary_source` — the URL a re-verifier should start from
- `notes` — quirks specific to this jurisdiction (multi-hauler caveats, single-family-home assumption, recent rule changes)
- `bins` — the bins residents actually have. The `id` must be one of `recycling`, `compost`, `landfill`, `hazardous`, `special` (the closed routing vocabulary). The `label` and `color` capture local detail.
- `rules` — one entry per material category. The `category` field must reference an `id` from `taxonomy.json`. If your city has rules for a material that isn't in the taxonomy, see "Adding a taxonomy category" below.
- `edge_cases` — items the agent might mis-identify. Skip if not applicable.

For each rule, fill in the `source` block with the URL the rule came from, today's date, the publisher (city name or hauler name), and the source license:

| `source_license` | Use when |
|---|---|
| `cc0` | Source is dedicated to the public domain (rare for city pages) |
| `cc_by` | Source is CC-BY licensed |
| `cc_by_sa` | Source is CC-BY-SA licensed |
| `proprietary` | Default for most city and hauler pages — wording is © them, the underlying facts are uncopyrightable (Feist v. Rural) |
| `unknown` | Source has no clear license marking |

The `archive_url` field is optional but **strongly encouraged**. After verifying the page, save it to the [Wayback Machine](https://web.archive.org/save) and put the snapshot URL there. This preserves the audit trail when the upstream page reorganizes.

### 5. Validate locally

```sh
binwise validate
binwise format
binwise validate   # confirm the format pass didn't break anything
```

Fix any errors. Warnings (canonicalization, staleness) are not blocking but are worth resolving.

### 6. Open a PR

Title: `Add <City>, <State>` or `Update <City>: <one-line summary>`.

Body, terse:

```
Adds <city>, <state>, sourced from <publisher>'s <page name> at <URL>.
Verified <today>. <Notable rule choices, if any, e.g. "compost accepts plastic-lined paper, unlike most cities">.
```

CI will run schema validation, taxonomy enforcement, format check. Address any failures before requesting review.

---

## Reviewing rules: the 1-2-2 standard

Reviewer threshold is determined by source authority, encoded in the validator (`KNOWN_HAULER_DOMAINS`):

| Source kind | Reviewers needed |
|---|---|
| `.gov` page | 1 |
| Known hauler domain | 1 |
| Other public published page | 2 |
| Blog, forum, AI summary | rejected |

A PR landing at `verification_level: unverified` only needs schema validation — it lands as a marker for community follow-up. Laddering up to `reviewed` is a separate PR by a reviewer who has read every source URL.

**Taxonomy changes always need 2 reviewers**, regardless of source. A category added to `taxonomy.json` affects every consumer of the dataset.

---

## Adding a taxonomy category

If your city has a material category not in `taxonomy.json` (e.g., a rule for "fluorescent ballasts" and there's no matching id):

1. Open `taxonomy.json`. Add a new entry with:
   - `id` — lowercase, snake_case, descriptive
   - `name` — human-readable
   - `aliases` — synonyms the agent might use
   - `examples` — concrete example items
   - `calrecycle_type` — match to a CalRecycle Material Type if possible (see [the list](https://www2.calrecycle.ca.gov/WasteCharacterization/MaterialType))
2. Reference the new id in your city PR's `category` field.
3. Same PR. The taxonomy diff gets reviewed first by the merge-gate logic.

Don't invent a category if one already exists. Look at `aliases` — your material may already be covered. Lookup tip: `grep -i <your-material> taxonomy.json`.

---

## Public-sources-only rule for industry contributors

If you're employed by a hauler, recycling industry trade group, or a municipal solid-waste department, **disclose this in your PR description**. Disclosure isn't a disqualifier — industry insiders often have the most accurate knowledge.

But: **source rules from public documents only**. Internal training material, unreleased policy drafts, draft PDFs, internal Slack messages, and non-public communications are out of bounds even when accurate. Two reasons:

1. The audit trail must be replicable by any reader. A non-public source can't be cited or rechecked.
2. Your employer's IP and confidentiality obligations are theirs to honor, not ours to navigate.

If you know a rule is wrong because of internal knowledge, the right move is to ask your employer to update their public-facing page, then cite the updated public page in your PR.

---

## Disputes

If you think a rule in an existing city file is wrong, **file an issue with a counter-source URL** and the `dispute` label. Don't open a PR overwriting the rule until the dispute is resolved.

The dispute process (DESIGN.md §6 has the full version):

- **Typo or formatting** — any maintainer can fix directly, no waiting period.
- **Substantive rule change** with a clear authoritative counter-source — file maintainer (the latest committer of the city file) responds within 4 weeks. After that, the top-level maintainer adjudicates.
- **Conflicting authoritative sources** — both cited in the file's `notes`, the rule defaults to the city page, and the discrepancy is logged with the `conflicting-sources` label until clarified by direct contact with the publisher.

Issues without a counter-source URL are closed.

---

## Style

- **No emojis.** This is a project rule. Apply to commit messages, PR descriptions, and any text in city files (`notes`, `prep`, `why`, etc.).
- **Terse writing.** A `prep` field reads `"rinse, lids on"`, not `"Please rinse out the container thoroughly and remember to keep the lid attached so it doesn't get lost in transit."`
- **Plain English in `if` conditions.** `"clean (no grease or cheese residue)"`, not `"contamination_level=clean"`. The reference consumer is an LLM that reads the condition; treat it like a smart reader, not a parser.
- **Sentence-case `name` fields**, not Title Case. `"San Francisco"`, but `"Glass bottles and jars"`.

---

## Maintainer conduct

Maintainers are listed in [MAINTAINERS.md](MAINTAINERS.md). The current maintainer set merges PRs and adjudicates disputes. New maintainers are added by invitation after demonstrated contribution (typically 3+ merged PRs or significant taxonomy/tooling work).

Maintainers do not push to a city file without disclosing in the commit message that they are not the file's named maintainer or a resident of that jurisdiction.

### v0 self-merge escape clause

This project starts with a single maintainer. Until **at least two maintainers** are listed in MAINTAINERS.md, the maintainer may self-merge their own PRs after:

1. **Either** a 24-hour open-PR cooling-off period from when the PR is opened, **or** an external review comment (any GitHub user — drive-by reviewers count).
2. All CI gates green.
3. PR description states explicitly that this is a self-merge under the v0 escape clause.

This clause exists because requiring two maintainers when only one exists would block all forward motion. It is removed automatically the moment a second maintainer is added to MAINTAINERS.md — at that point, all PRs require approval from a maintainer who is not the author.

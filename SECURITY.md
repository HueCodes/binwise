# Security Policy

binwise has two attack surfaces worth thinking about:

1. **Code.** The `binwise` Python package — validator, reference agent, and web demo — with the usual code-execution and supply-chain concerns.
2. **Data.** The dataset under `cities/`. A malicious PR that lands a wrong rule has real-world consequences (someone routes a lithium battery into the curbside cart). CI gates and the 1-2-2 reviewer rule in [CONTRIBUTING.md](CONTRIBUTING.md) are meant to catch this; report any path you find that bypasses them.

## In scope

- Code-execution, arbitrary-file-write, or path-traversal vulnerabilities in the validator, agent, or web demo.
- Dependency vulnerabilities introduced by `pyproject.toml`.
- CI bypass paths that let a malicious PR merge without the required reviewer count.
- Data-integrity issues that break schema invariants in non-obvious ways (e.g. a JSON shape that validates but is interpreted inconsistently by consumers).

## Out of scope

- Disagreement about a recycling rule — that's a dispute, file an issue with a counter-source URL (see [DESIGN.md §6](DESIGN.md)).
- The reference agent's verdict being wrong on your photo — open a regular issue.
- Vulnerabilities in upstream dependencies that are already disclosed there — file upstream first; we'll bump after.

## Reporting

Use [GitHub Security Advisories](https://github.com/HueCodes/binwise/security/advisories/new) for private disclosure. Expect an acknowledgement within ~7 days; the project is maintained by a single person and SLAs are best-effort. For critical issues that justify out-of-band contact, the project lead's GitHub handle is in [MAINTAINERS.md](MAINTAINERS.md).

Please do not file public issues for vulnerabilities, and do not exploit any hosted demo (when it exists, it carries no user data).

## Disclosure

Coordinated: report → fix lands → public advisory. Reporters are credited in the advisory unless they ask not to be named.

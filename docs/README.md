# Docs

Entry point for everything that is not code. Open work is tracked in [`../BACKLOG.md`](../BACKLOG.md); this folder holds the concepts behind it.

## Layout

| Folder | What lives here |
|---|---|
| [`architecture/`](architecture/) | How the system is built and where it is going |
| [`features/`](features/) | One concept doc per feature: goal, decisions, plan, status |
| [`research/`](research/) | Feasibility studies and source surveys that informed features |
| [`operations/`](operations/) | Runbooks and reference for running the live site |

Also at the repo root: [`README.md`](../README.md) (how to run the pipelines, season rollover checklist) and [`AGENTS.md`](../AGENTS.md) (rules for coding agents).

## Index

### Architecture

- [ARCHITECTURE.md](architecture/ARCHITECTURE.md): pipelines, data flow, integration invariants (authoritative)
- [VISION.md](architecture/VISION.md): why the project exists, product direction
- [next-generation-design.md](architecture/next-generation-design.md): multi-country target picture of March 2026

### Features

| Feature | Status | Backlog |
|---|---|---|
| [Team map](features/team-map.md) | shipped | Done |
| [Club logos](features/club-logos/plan.md) ([rights research](features/club-logos/rights-research.md), [inventory](features/club-logos/inventory.md)) | partly shipped | Open |
| [Game report sharing](features/game-report-sharing.md) | partly shipped | Open (P1) |
| [SEO](features/seo.md) | mostly shipped | Open (P1) |
| [Home/away social](features/home-away-social.md) | partly shipped, unverified | Ideas |
| [Auth and premium access](features/auth-premium-access.md) | idea | none |

### Research

- [League portals](research/league-portals.md): portals and JSON backends of SE, FI, CH, CZ
- [Scorer names feasibility](research/scorer-names-feasibility.md)

### Operations

- [Google reindexing](operations/google-reindexing.md) with [priority URLs](operations/google-reindex-urls.txt)
- [Analytics events](operations/analytics-events.md): PostHog event names and properties

## Writing a feature doc

Create `features/<name>.md` (or a folder `features/<name>/` with `plan.md` plus supporting files). Start with:

```markdown
# <Feature name>

> **Status:** open | partly shipped | shipped | idea · Backlog: [<item>](../../BACKLOG.md#open) · Code: `src/...`
```

Then: goal, decisions (who, when), approach, open questions. Keep the `Status` line current when the backlog item moves, and add the feature to the table above.

Docs-only changes do not trigger a production deploy (`paths-ignore` in `.github/workflows/deploy.yml`).

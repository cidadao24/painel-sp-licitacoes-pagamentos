# Repository Repurpose Plan

This repository is being repurposed from the old São Paulo procurement dashboard into **Bureaucracy Radar**.

## Status

The legacy procurement panel remains in place for reference, but new work should happen under `bureaucracy-radar/`.

## New target product

Bureaucracy Radar monitors official public sources, stores snapshots, detects meaningful changes, and produces plain-language alerts for human review.

## Immediate priorities

1. Build and stabilize the Python watcher pipeline.
2. Add a lightweight review dashboard.
3. Add scheduled automation with GitHub Actions.
4. Gradually retire or archive the old procurement-specific site.

## Suggested later cleanup

- replace the root README with Bureaucracy Radar documentation
- move legacy procurement assets into a `legacy/` folder
- republish GitHub Pages with the new dashboard

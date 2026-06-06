# Table Title Prefer Rules Update

Date: 2026-06-07

## Goal

Reduce review noise for high-confidence HK and US consolidated statement titles.

## Change

Added `prefer` title patterns to:

- `rules/us/table_titles.yml`
- `rules/hk/table_titles.yml`

The classifier already treats `prefer` matches as confidence `0.95`, which can
avoid review when scope is `consolidated`.

## Boundary

This only upgrades exact, explicit consolidated statement titles already present
in the rule packs. It does not make fuzzy matches trusted, and it does not
change parent-company exclusions.

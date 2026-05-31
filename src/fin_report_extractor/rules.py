from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


RULE_FILENAMES = [
    "table_titles.yml",
    "concept_aliases.yml",
    "unit_patterns.yml",
    "period_patterns.yml",
    "note_roles.yml",
    "validation_overrides.yml",
]


@dataclass(frozen=True)
class MarketRulePack:
    market: str
    version_hash: str
    table_titles: dict[str, Any]
    concept_aliases: dict[str, Any]
    unit_patterns: dict[str, Any]
    period_patterns: dict[str, Any]
    note_roles: dict[str, Any]
    validation_overrides: dict[str, Any]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Rule file must contain a mapping: {path}")

    return data


def _hash_rule_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_market_rule_pack(rules_root: Path, market: str) -> MarketRulePack:
    market_dir = rules_root / market
    paths = [market_dir / filename for filename in RULE_FILENAMES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing rule files: {', '.join(missing)}")

    loaded = {path.name: _load_yaml(path) for path in paths}

    return MarketRulePack(
        market=market,
        version_hash=_hash_rule_files(paths),
        table_titles=loaded["table_titles.yml"],
        concept_aliases=loaded["concept_aliases.yml"],
        unit_patterns=loaded["unit_patterns.yml"],
        period_patterns=loaded["period_patterns.yml"],
        note_roles=loaded["note_roles.yml"],
        validation_overrides=loaded["validation_overrides.yml"],
    )

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

from peg_rules import (
    RULES_PATH,
    grammar_sha256,
    load_yaml,
    parse_grammar,
    rule_filename,
    spec_for_rule,
    yaml_text,
)


def merged_spec(spec: dict, path: Path) -> dict:
    if not path.exists():
        return spec
    old = load_yaml(path)
    if old.get("peg", {}).get("rule") != spec["peg"]["rule"]:
        raise ValueError(f"{path}: specification is for the wrong PEG rule")
    migration = old.get("migration")
    if not isinstance(migration, dict):
        raise ValueError(f"{path}: missing migration mapping")
    old_hash = old.get("peg", {}).get("body_sha256")
    new_hash = spec["peg"]["body_sha256"]
    if old_hash and old_hash != new_hash:
        migration = dict(migration)
        migration["status"] = "needs-rereview"
        spec["peg"]["previous_body_sha256"] = old_hash
    elif old.get("peg", {}).get("previous_body_sha256"):
        spec["peg"]["previous_body_sha256"] = old["peg"]["previous_body_sha256"]
    elif migration.get("status") == "needs-review":
        # Refresh generator-owned suggestions until a human confirms the rule.
        migration = dict(migration)
        migration["classification"]["suggested"] = spec["migration"][
            "classification"
        ]["suggested"]
        migration["parser"]["strategy"] = spec["migration"]["parser"]["strategy"]
        migration["syntax"]["nodes"] = spec["migration"]["syntax"]["nodes"]
        migration["pyo3_conversion"]["route"] = spec["migration"][
            "pyo3_conversion"
        ]["route"]
    spec["migration"] = migration
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate one YAML migration specification per PEG rule."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale files without modifying the repository",
    )
    args = parser.parse_args()

    grammar_text, rules = parse_grammar()
    names = {rule.name for rule in rules}
    RULES_PATH.mkdir(parents=True, exist_ok=True)
    expected_names = set()
    stale = False

    for rule in rules:
        path = RULES_PATH / rule_filename(rule.name)
        expected_names.add(path.name)
        spec = merged_spec(spec_for_rule(grammar_text, rule, names), path)
        generated = yaml_text(spec)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if generated == current:
            continue
        if args.check:
            stale = True
            print(f"stale: {path.relative_to(path.parents[2])}")
            if current:
                diff = difflib.unified_diff(
                    current.splitlines(),
                    generated.splitlines(),
                    fromfile=str(path),
                    tofile=f"{path} (generated)",
                    n=3,
                )
                print("\n".join(list(diff)[:80]))
        else:
            path.write_text(generated, encoding="utf-8")
            print(f"generated: {path.relative_to(path.parents[2])}")

    extras = {
        path.name
        for path in RULES_PATH.glob("*.yaml")
        if path.name not in expected_names
    }
    for extra in sorted(extras):
        path = RULES_PATH / extra
        if args.check:
            stale = True
            print(f"obsolete: {path.relative_to(path.parents[2])}")
        else:
            path.unlink()
            print(f"removed obsolete: {path.relative_to(path.parents[2])}")

    summary = RULES_PATH.parent / "grammar.yaml"
    summary_data = {
        "schema_version": 1,
        "grammar": {
            "file": "enaml/core/parser/enaml.gram",
            "sha256": grammar_sha256(grammar_text),
            "rule_count": len(rules),
            "spec_directory": "parser_migration/rules",
        },
        "inventory": {
            "reviewed": sum(
                1
                for rule in rules
                if (
                    (RULES_PATH / rule_filename(rule.name)).exists()
                    and load_yaml(
                        RULES_PATH / rule_filename(rule.name)
                    )["migration"]["status"]
                    in {"confirmed", "implemented"}
                )
            ),
            "implemented": sum(
                1
                for rule in rules
                if (
                    (RULES_PATH / rule_filename(rule.name)).exists()
                    and load_yaml(
                        RULES_PATH / rule_filename(rule.name)
                    )["migration"]["status"]
                    == "implemented"
                )
            ),
        },
    }
    summary_text = yaml_text(summary_data)
    if not args.check:
        summary.write_text(summary_text, encoding="utf-8")
    else:
        current = summary.read_text(encoding="utf-8") if summary.exists() else ""
        if current != summary_text:
            stale = True
            print(f"stale: {summary.relative_to(summary.parents[1])}")

    if stale:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

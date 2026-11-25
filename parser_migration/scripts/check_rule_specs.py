#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from peg_rules import (
    ALLOWED_CLASSIFICATIONS,
    ALLOWED_STATUSES,
    GRAMMAR_PATH,
    RULES_PATH,
    REPOSITORY_ROOT,
    grammar_sha256,
    inventory_nodes,
    load_yaml,
    parse_grammar,
    rule_filename,
    spec_for_rule,
)


def errors_for_rule(path: Path, spec: dict, expected: dict, strict: bool) -> list[str]:
    errors: list[str] = []
    prefix = path.relative_to(REPOSITORY_ROOT).as_posix()

    if spec.get("schema_version") != 1:
        errors.append(f"{prefix}: schema_version must be 1")
    peg = spec.get("peg")
    evidence = spec.get("evidence")
    migration = spec.get("migration")
    if not isinstance(peg, dict) or not isinstance(evidence, dict) or not isinstance(migration, dict):
        errors.append(f"{prefix}: peg, evidence, and migration mappings are required")
        return errors

    for key in ("rule", "file", "start_line", "end_line", "ownership",
                "return_type", "memoized", "body_sha256",
                "previous_body_sha256"):
        if key not in peg:
            errors.append(f"{prefix}: missing peg.{key}")
    for key in ("alternatives", "left_recursive", "references", "literals",
                "soft_keywords", "ast_targets", "ast_references",
                "version_gates"):
        if key not in evidence:
            errors.append(f"{prefix}: missing evidence.{key}")

    for section in ("peg", "grammar", "evidence"):
        actual_section = spec.get(section)
        expected_section = expected.get(section)
        if section == "peg" and isinstance(actual_section, dict):
            actual_section = dict(actual_section)
            expected_section = dict(expected_section or {})
            expected_section["previous_body_sha256"] = actual_section.get(
                "previous_body_sha256"
            )
        if section in spec and section in expected and actual_section != expected_section:
            errors.append(f"{prefix}: generated {section} data is stale")

    status = migration.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append(f"{prefix}: invalid migration.status {status!r}")

    classification = migration.get("classification")
    if not isinstance(classification, dict):
        errors.append(f"{prefix}: migration.classification must be a mapping")
    else:
        suggested = classification.get("suggested")
        confirmed = classification.get("confirmed")
        if suggested not in ALLOWED_CLASSIFICATIONS:
            errors.append(f"{prefix}: invalid suggested classification {suggested!r}")
        if confirmed is not None and confirmed not in ALLOWED_CLASSIFICATIONS:
            errors.append(f"{prefix}: invalid confirmed classification {confirmed!r}")

    for nested in ("parser", "syntax", "recovery", "pyo3_conversion", "tests", "review"):
        if not isinstance(migration.get(nested), dict):
            errors.append(f"{prefix}: migration.{nested} must be a mapping")

    parser_info = migration.get("parser", {})
    syntax = migration.get("syntax", {})
    conversion = migration.get("pyo3_conversion", {})
    tests = migration.get("tests", {})
    nodes = inventory_nodes()
    unknown_nodes = set(syntax.get("nodes", [])) - nodes
    if unknown_nodes:
        errors.append(
            f"{prefix}: unknown Rowan nodes: {', '.join(sorted(unknown_nodes))}"
        )
    selected_class = (
        classification.get("confirmed") if isinstance(classification, dict) else None
    ) or (
        classification.get("suggested") if isinstance(classification, dict) else None
    )
    if selected_class and selected_class.startswith("pratt-"):
        if parser_info.get("strategy") != selected_class:
            errors.append(
                f"{prefix}: Pratt classification requires matching parser.strategy"
            )
    if selected_class == "pratt-infix":
        for field in ("binding_power", "associativity"):
            if status in {"confirmed", "implemented"} and parser_info.get(field) is None:
                errors.append(f"{prefix}: confirmed Pratt rule needs parser.{field}")
    if selected_class == "pratt-prefix":
        if status in {"confirmed", "implemented"} and parser_info.get("binding_power") is None:
            errors.append(f"{prefix}: confirmed prefix rule needs parser.binding_power")
    if conversion.get("route") not in {"direct-python-ast", "no-ast"}:
        errors.append(f"{prefix}: pyo3_conversion.route is invalid")

    if status in {"confirmed", "implemented"} or strict:
        if migration.get("classification", {}).get("confirmed") is None:
            errors.append(f"{prefix}: classification.confirmed is required")
        if parser_info.get("entry") is None:
            errors.append(f"{prefix}: parser.entry is required")
        if not syntax.get("first_tokens"):
            errors.append(f"{prefix}: syntax.first_tokens is required")
        if not syntax.get("trivia_contract_reviewed"):
            errors.append(f"{prefix}: syntax.trivia_contract_reviewed must be true")
        if conversion.get("reviewed") is not True:
            errors.append(f"{prefix}: pyo3_conversion.reviewed must be true")
        if not tests.get("valid_fixtures"):
            errors.append(f"{prefix}: at least one valid fixture is required")
        if not tests.get("round_trip"):
            errors.append(f"{prefix}: round_trip must be true")

    if status == "implemented":
        if not tests.get("invalid_fixtures"):
            errors.append(f"{prefix}: implemented rule needs invalid fixtures")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PEG-to-parser YAML migration specifications."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="require reviewed migration decisions for every rule",
    )
    args = parser.parse_args()

    grammar_text, rules = parse_grammar()
    names = {rule.name for rule in rules}
    expected_files = {rule_filename(rule.name) for rule in rules}
    actual_files = {path.name for path in RULES_PATH.glob("*.yaml")}
    errors: list[str] = []

    missing = expected_files - actual_files
    extra = actual_files - expected_files
    for name in sorted(missing):
        errors.append(f"missing parser_migration/rules/{name}")
    for name in sorted(extra):
        errors.append(f"obsolete parser_migration/rules/{name}")

    for rule in rules:
        path = RULES_PATH / rule_filename(rule.name)
        if not path.exists():
            continue
        try:
            spec = load_yaml(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        expected = spec_for_rule(grammar_text, rule, names)
        if spec.get("peg", {}).get("body_sha256") != expected["peg"]["body_sha256"]:
            errors.append(
                f"{path.relative_to(REPOSITORY_ROOT)}: PEG body hash changed"
            )
        errors.extend(errors_for_rule(path, spec, expected, args.strict))

    summary_path = RULES_PATH.parent / "grammar.yaml"
    if not summary_path.exists():
        errors.append("missing parser_migration/grammar.yaml")
    else:
        try:
            summary = load_yaml(summary_path)
            if summary.get("grammar", {}).get("sha256") != grammar_sha256(grammar_text):
                errors.append("parser_migration/grammar.yaml: grammar hash is stale")
            if summary.get("grammar", {}).get("rule_count") != len(rules):
                errors.append("parser_migration/grammar.yaml: rule count is stale")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    if errors:
        print("\n".join(errors))
        return 1
    print(f"validated {len(rules)} PEG rule specifications")
    return 0


if __name__ == "__main__":
    sys.exit(main())

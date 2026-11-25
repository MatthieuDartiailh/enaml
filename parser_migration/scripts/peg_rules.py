from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GRAMMAR_PATH = REPOSITORY_ROOT / "enaml/core/parser/enaml.gram"
RULES_PATH = REPOSITORY_ROOT / "parser_migration/rules"
NODE_INVENTORY_PATH = (
    REPOSITORY_ROOT
    / "docs/source/developer_notes/lsp_parser_rowan_nodes.rst"
)

ALLOWED_CLASSIFICATIONS = {
    "pratt-infix",
    "pratt-prefix",
    "pratt-postfix",
    "pratt-special",
    "recursive-descent",
    "list",
    "lexer",
    "recovery",
    "semantic",
    "not-in-cst",
}

ALLOWED_STATUSES = {
    "needs-review",
    "needs-rereview",
    "confirmed",
    "implemented",
}

PRATT_INFIX = {
    "bitwise_or",
    "bitwise_xor",
    "bitwise_and",
    "shift_expr",
    "sum",
    "term",
    "power",
}

PRATT_PREFIX = {"factor", "inversion", "await_primary"}

PRATT_POSTFIX = {
    "attr",
    "dec_primary",
    "dotted_name",
    "primary",
    "t_primary",
}

PRATT_SPECIAL = {
    "annotated_rhs",
    "assignment_expression",
    "comparison",
    "conjunction",
    "disjunction",
    "expression",
    "expressions",
    "genexp",
    "listcomp",
    "setcomp",
    "dictcomp",
    "group",
    "lambdef",
    "named_expression",
    "star_expression",
    "star_expressions",
    "star_named_expression",
    "yield_expr",
}

LIST_RULES = {
    "args",
    "arguments",
    "decorators",
    "del_targets",
    "double_starred_kvpairs",
    "items_pattern",
    "keyword_patterns",
    "kwargs",
    "name_or_attr",
    "open_sequence_pattern",
    "params",
    "parameters",
    "lambda_parameters",
    "positional_patterns",
    "pragmas",
    "slices",
    "star_expressions",
    "star_named_expressions",
    "star_targets",
    "star_targets_list_seq",
    "star_targets_tuple_seq",
    "statements",
    "template_args",
    "template_ids",
    "template_params",
    "type_param_seq",
    "type_params",
}

SOFT_KEYWORDS = {
    "_",
    "alias",
    "attr",
    "case",
    "const",
    "enamldef",
    "event",
    "func",
    "lazy",
    "match",
    "pragma",
    "template",
    "type",
}

AST_TO_NODE = {
    "AliasExpr": "ALIAS_EXPR",
    "And": "BOOL_EXPR",
    "AnnAssign": "ANN_ASSIGN_STMT",
    "Assert": "ASSERT_STMT",
    "Assign": "ASSIGN_STMT",
    "AsyncFunctionDef": "ASYNC_FUNCTION_DEF",
    "AsyncFor": "ASYNC_FOR_STMT",
    "AsyncFuncDef": "DECL_FUNC",
    "AsyncWith": "ASYNC_WITH_STMT",
    "Attribute": "ATTR_EXPR",
    "AugAssign": "AUG_ASSIGN_STMT",
    "Await": "AWAIT_EXPR",
    "BinOp": "BINARY_EXPR",
    "Binding": "BINDING",
    "BoolOp": "BOOL_EXPR",
    "Break": "BREAK_STMT",
    "Call": "CALL_EXPR",
    "ChildDef": "CHILD_DEF",
    "ClassDef": "CLASS_DEF",
    "Compare": "COMPARE_EXPR",
    "ConstExpr": "CONST_EXPR",
    "Continue": "CONTINUE_STMT",
    "Delete": "DEL_STMT",
    "Dict": "DICT_EXPR",
    "DictComp": "DICT_COMP",
    "EnamlDef": "ENAMLDEF",
    "ExBinding": "EX_BINDING",
    "Expr": "EXPR_STMT",
    "FormattedValue": "FSTRING_FIELD",
    "FunctionDef": "FUNCTION_DEF",
    "GeneratorExp": "GENERATOR_EXPR",
    "Global": "GLOBAL_STMT",
    "If": "IF_STMT",
    "IfExp": "COND_EXPR",
    "Import": "IMPORT_STMT",
    "ImportFrom": "FROM_IMPORT_STMT",
    "Interpolation": "TSTRING_FIELD",
    "JoinedStr": "FSTRING",
    "Lambda": "LAMBDA_EXPR",
    "List": "LIST_EXPR",
    "ListComp": "LIST_COMP",
    "Match": "MATCH_STMT",
    "MatchAs": "AS_PATTERN",
    "MatchClass": "CLASS_PATTERN",
    "MatchMapping": "MAPPING_PATTERN",
    "MatchOr": "OR_PATTERN",
    "MatchSequence": "SEQUENCE_PATTERN",
    "MatchStar": "STAR_PATTERN",
    "MatchValue": "VALUE_PATTERN",
    "Module": "ROOT",
    "NamedExpr": "NAMED_EXPR",
    "Nonlocal": "NONLOCAL_STMT",
    "OperatorExpr": "OPERATOR_EXPR",
    "Pass": "PASS_STMT",
    "Pragma": "PRAGMA",
    "PragmaArg": "PRAGMA_ARG",
    "Raise": "RAISE_STMT",
    "Return": "RETURN_STMT",
    "Set": "SET_EXPR",
    "SetComp": "SET_COMP",
    "Starred": "STARRED_EXPR",
    "StorageExpr": "STORAGE_EXPR",
    "Subscript": "INDEX_EXPR",
    "Template": "TEMPLATE",
    "TemplateArguments": "TEMPLATE_ARG_LIST",
    "TemplateIdentifiers": "TEMPLATE_ID_LIST",
    "TemplateInst": "TEMPLATE_INST",
    "TemplateInstBinding": "TEMPLATE_INST_BINDING",
    "TemplateParameters": "TEMPLATE_PARAM_LIST",
    "TemplateStr": "TSTRING",
    "Try": "TRY_STMT",
    "TryStar": "TRY_STMT",
    "Tuple": "TUPLE_EXPR",
    "TypeAlias": "TYPE_ALIAS_STMT",
    "UnaryOp": "UNARY_EXPR",
    "While": "WHILE_STMT",
    "With": "WITH_STMT",
    "Yield": "YIELD_EXPR",
    "YieldFrom": "YIELD_FROM_EXPR",
    "comprehension": "FOR_IF_CLAUSE",
    "keyword": "KW_ARG",
    "match_case": "MATCH_CASE",
    "withitem": "WITH_ITEM",
}

FUNCTIONAL_PEG_RULES = {
    "invalid_parameters_helper",
    "invalid_lambda_parameters_helper",
    "template_id_termination",
    "t_lookahead",
    "func_type_comment",
}


@dataclass(frozen=True)
class PegRule:
    name: str
    start_line: int
    end_line: int
    body: str
    return_type: str | None
    memoized: bool

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body.encode()).hexdigest()


def repository_relative(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def match_rule_header(line: str) -> dict[str, Any] | None:
    """Parse a PEG header, including nested brackets in its return type."""
    name_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", line)
    if not name_match:
        return None
    name = name_match.group(1)
    position = name_match.end()
    return_type = None
    if position < len(line) and line[position] == "[":
        start = position + 1
        depth = 1
        position += 1
        while position < len(line) and depth:
            if line[position] == "[":
                depth += 1
            elif line[position] == "]":
                depth -= 1
            position += 1
        if depth:
            return None
        return_type = line[start : position - 1]
    while position < len(line) and line[position].isspace():
        position += 1
    memoized = False
    if position < len(line) and line[position] == "(":
        end = line.find(")", position + 1)
        if end == -1:
            return None
        memoized = "memo" in line[position + 1 : end].split()
        position = end + 1
    while position < len(line) and line[position].isspace():
        position += 1
    if position >= len(line) or line[position] != ":":
        return None
    return {
        "name": name,
        "return_type": return_type,
        "memoized": memoized,
        "rest": line[position + 1 :].lstrip(),
    }


def grammar_sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse_grammar(path: Path = GRAMMAR_PATH) -> tuple[str, list[PegRule]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    headers: list[tuple[int, dict[str, Any]]] = []
    for index, line in enumerate(lines):
        header = match_rule_header(line.rstrip("\n"))
        if header:
            headers.append((index, header))

    rules: list[PegRule] = []
    for position, (start, header) in enumerate(headers):
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        body = "".join(lines[start:end]).rstrip("\n") + "\n"
        rules.append(
            PegRule(
                name=header["name"],
                start_line=start + 1,
                end_line=end,
                body=body,
                return_type=header["return_type"],
                memoized=header["memoized"],
            )
        )
    names = [rule.name for rule in rules]
    if len(names) != len(set(names)):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise ValueError(f"duplicate PEG rule names: {duplicates}")
    return text, rules


def quoted_literals(body: str) -> list[str]:
    values = []
    for match in re.finditer(r"""(['"])(?:(?!\1).)*\1""", body):
        value = match.group(0)[1:-1]
        if value:
            values.append(value)
    return sorted(set(values))


def peg_syntax(body: str) -> str:
    """Remove actions, comments, and the rule header from a PEG body."""
    lines = body.splitlines(keepends=True)
    if lines:
        lines[0] = lines[0].split(":", 1)[1] if ":" in lines[0] else ""
    source = "".join(lines)
    output: list[str] = []
    index = 0
    action_depth = 0
    quote: str | None = None
    escaped = False
    while index < len(source):
        char = source[index]
        if quote:
            if action_depth == 0:
                output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            if action_depth == 0:
                output.append(char)
            index += 1
            continue
        if char == "#":
            newline = source.find("\n", index)
            if newline == -1:
                break
            if action_depth == 0:
                output.append("\n")
            index = newline + 1
            continue
        if char == "{":
            action_depth += 1
        elif char == "}" and action_depth:
            action_depth -= 1
        elif action_depth == 0:
            output.append(char)
        index += 1
    return "".join(output)


def ast_targets(body: str) -> list[str]:
    return sorted(
        set(
            re.findall(
                r"\b(?:ast|enaml_ast)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                body,
            )
        )
    )


def ast_references(body: str) -> list[str]:
    return sorted(
        set(
            re.findall(
                r"\b(?:ast|enaml_ast)\.([A-Za-z_][A-Za-z0-9_]*)",
                body,
            )
        )
    )


def version_gates(body: str) -> list[str]:
    gates = set(re.findall(r"\(\s*3,\s*(?:[0-9]+)\s*\)", body))
    return sorted(".".join(re.findall(r"\d+", gate)) for gate in gates)


def alternative_count(body: str) -> int:
    inline = 1 if ":" in body.splitlines()[0] else 0
    alternatives = len(re.findall(r"^\s*\|", body, re.MULTILINE))
    return alternatives if alternatives else inline


def rule_references(body: str, names: set[str]) -> list[str]:
    without_literals = re.sub(
        r"""(['"])(?:(?!\1).)*\1""", " ", body
    )
    candidates = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", without_literals)
    return sorted({candidate for candidate in candidates if candidate in names})


def suggested_classification(rule: PegRule, references: list[str]) -> str:
    if rule.name.startswith("invalid_"):
        return "recovery"
    if rule.name in PRATT_INFIX:
        return "pratt-infix"
    if rule.name in PRATT_PREFIX:
        return "pratt-prefix"
    if rule.name in PRATT_POSTFIX:
        return "pratt-postfix"
    if rule.name in PRATT_SPECIAL:
        return "pratt-special"
    if rule.name in LIST_RULES or re.search(
        r"(?:,|;)\s*'\.|,\s*'\.|,['\"]\.", rule.body
    ):
        return "list"
    if rule.name in FUNCTIONAL_PEG_RULES:
        return "not-in-cst"
    if rule.name in {
        "fstring_conversion",
        "fstring_format_spec",
        "fstring_full_format_spec",
        "fstring_mid",
        "fstring_replacement_field",
        "strings",
        "tstring_conversion",
        "tstring_format_spec",
        "tstring_full_format_spec",
        "tstring_mid",
        "tstring_replacement_field",
    }:
        return "recursive-descent"
    return "recursive-descent"


def syntax_node_suggestions(targets: list[str]) -> list[str]:
    return sorted({AST_TO_NODE[target] for target in targets if target in AST_TO_NODE})


def default_migration(rule: PegRule, classification: str, nodes: list[str]) -> dict[str, Any]:
    lowerer = "direct-python-ast" if ast_targets(rule.body) else "no-ast"
    return {
        "status": "needs-review",
        "classification": {
            "suggested": classification,
            "confirmed": None,
        },
        "parser": {
            "entry": None,
            "strategy": classification,
            "binding_power": None,
            "associativity": None,
            "expression_context": None,
        },
        "syntax": {
            "nodes": nodes,
            "trivia_contract_reviewed": False,
            "first_tokens": [],
            "follow_tokens": [],
        },
        "recovery": {
            "sync_tokens": [],
            "diagnostic": None,
        },
        "pyo3_conversion": {
            "route": lowerer,
            "reviewed": False,
        },
        "tests": {
            "valid_fixtures": [],
            "invalid_fixtures": [],
            "round_trip": False,
            "precedence": False,
            "version_gate": False,
        },
        "review": {
            "owner": None,
            "notes": [],
        },
    }


def spec_for_rule(grammar_text: str, rule: PegRule, all_names: set[str]) -> dict[str, Any]:
    syntax = peg_syntax(rule.body)
    refs = rule_references(syntax, all_names)
    literals = quoted_literals(syntax)
    targets = ast_targets(rule.body)
    classification = suggested_classification(rule, refs)
    ownership = (
        "enaml"
        if rule.start_line < 456
        else "python-recovery"
        if rule.name.startswith("invalid_")
        else "python"
    )
    left_recursive = bool(
        re.search(
            rf"^\s*\|\s*(?:[A-Za-z_]\w*\s*=\s*)?{re.escape(rule.name)}\b",
            syntax,
            re.MULTILINE,
        )
    )
    return {
        "schema_version": 1,
        "peg": {
            "rule": rule.name,
            "file": repository_relative(GRAMMAR_PATH),
            "start_line": rule.start_line,
            "end_line": rule.end_line,
            "ownership": ownership,
            "return_type": rule.return_type,
            "memoized": rule.memoized,
            "body_sha256": rule.body_sha256,
            "previous_body_sha256": None,
        },
        "grammar": {
            "sha256": grammar_sha256(grammar_text),
            "rule_count": len(all_names),
        },
        "evidence": {
            "alternatives": alternative_count(syntax),
            "left_recursive": left_recursive,
            "references": refs,
            "literals": literals,
            "soft_keywords": sorted(set(literals) & SOFT_KEYWORDS),
            "ast_targets": targets,
            "ast_references": ast_references(rule.body),
            "version_gates": version_gates(rule.body),
        },
        "migration": default_migration(
            rule, classification, syntax_node_suggestions(targets)
        ),
    }


def scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def dump_yaml(value: Any, indent: int = 0) -> list[str]:
    result: list[str] = []
    prefix = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                result.append(f"{prefix}{key}:")
                result.extend(dump_yaml(item, indent + 2))
            elif isinstance(item, (dict, list)):
                result.append(f"{prefix}{key}: []" if isinstance(item, list) else f"{prefix}{key}: {{}}")
            else:
                result.append(f"{prefix}{key}: {scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                raise TypeError("nested structured YAML lists are unsupported")
            result.append(f"{prefix}- {scalar(item)}")
    else:
        result.append(f"{prefix}{scalar(value)}")
    return result


def yaml_text(value: dict[str, Any]) -> str:
    return "\n".join(dump_yaml(value)) + "\n"


def parse_scalar(text: str) -> Any:
    if text == "null":
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text.startswith('"'):
        return json.loads(text)
    raise ValueError(f"unsupported YAML scalar: {text!r}")


def load_yaml(path: Path) -> dict[str, Any]:
    tokens: list[tuple[int, str, int]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ValueError(f"{path}:{number}: indentation must use two spaces")
        tokens.append((indent, raw.strip(), number))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(tokens):
            return {}, index
        is_list = tokens[index][1].startswith("- ")
        if is_list:
            result_list = []
            while index < len(tokens) and tokens[index][0] == indent:
                item_indent, text, number = tokens[index]
                if not text.startswith("- "):
                    break
                value = text[2:]
                if not value:
                    raise ValueError(
                        f"{path}:{number}: only scalar YAML lists are supported"
                    )
                result_list.append(parse_scalar(value))
                index += 1
            return result_list, index

        result: dict[str, Any] = {}
        while index < len(tokens) and tokens[index][0] == indent:
            _, text, number = tokens[index]
            if ":" not in text:
                raise ValueError(f"{path}:{number}: expected a mapping entry")
            key, raw_value = text.split(":", 1)
            raw_value = raw_value.strip()
            if raw_value == "[]":
                value: Any = []
                index += 1
            elif raw_value == "{}":
                value = {}
                index += 1
            elif raw_value:
                value = parse_scalar(raw_value)
                index += 1
            else:
                index += 1
                if index >= len(tokens) or tokens[index][0] <= indent:
                    value = {}
                else:
                    value, index = parse_block(index, indent + 2)
            if key in result:
                raise ValueError(f"{path}:{number}: duplicate key {key!r}")
            result[key] = value
        return result, index

    parsed, end = parse_block(0, 0)
    if end != len(tokens):
        _, _, number = tokens[end]
        raise ValueError(f"{path}:{number}: unexpected indentation")
    if not isinstance(parsed, dict):
        raise ValueError(f"{path}: document root must be a mapping")
    return parsed


def inventory_nodes(path: Path = NODE_INVENTORY_PATH) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"\* - ``([A-Z][A-Z0-9_]+)``(?:\s|`)", text))


def rule_filename(name: str) -> str:
    return f"{name}.yaml"

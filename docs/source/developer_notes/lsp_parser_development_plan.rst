.. _lsp_parser_development_plan:

==================================
Enaml LSP parser development plan
==================================

This is the execution plan for the :ref:`lsp_parser_architecture`.  Grammar
changes during implementation must follow the
:ref:`lsp_parser_grammar_maintenance` process.

Detailed parser development plan
================================

Phase 0: freeze the contract
----------------------------

Goals:

* select the existing Logos lexer API as the sole lexical source;
* define ``TokenKind`` and ``SyntaxKind``;
* define semantic-token/trivia ownership;
* specify parser target-version configuration;
* record current PEG provenance and file checksum.

Deliverables:

* ``enaml-syntax`` token and node-kind definitions;
* a parser token adapter;
* lexer reconstruction tests;
* a test helper that renders the entire Rowan tree, ranges, tokens, and text;
* the rule mapping manifest skeleton.

Exit criteria:

* every lexer fixture satisfies exact round-trip reconstruction;
* newline, indentation, f-string, t-string, soft-keyword, and operator fixtures
  have explicit token snapshots;
* no parser code depends directly on Logos internals other than through the
  adapter.

Phase 1: parser and Rowan infrastructure
----------------------------------------

Goals:

* build the event stream and forward-parent support;
* build a semantic-token cursor;
* implement token insertion, error, expectation, checkpoint, and marker
  primitives;
* define diagnostics with source ranges;
* define parser contexts and synchronization helpers.

Deliverables:

* empty-file and token-only root parsing;
* missing-token diagnostics without synthetic source;
* ``ERROR`` node construction;
* round-trip and incremental-equivalence tests for incomplete source.

Exit criteria:

* all currently emitted events produce a valid Rowan tree;
* every bump preserves attached trivia exactly;
* parser progress can be asserted in repetition and recovery loops.

Phase 2: Python expressions
---------------------------

Implement in this order:

1. atoms: names and numeric/string literals;
2. parentheses, tuples, lists, sets, dictionaries;
3. postfix calls, attributes, and subscriptions;
4. ``await``;
5. unary and ``**``;
6. multiplicative, additive, shift, bitwise operators;
7. comparison chains;
8. ``not``;
9. ``and`` and ``or`` chains;
10. conditional expressions;
11. lambdas;
12. named expressions and expression contexts;
13. yield forms and starred forms;
14. comprehensions, calls, arguments, slices, and assignment targets;
15. f-string/t-string replacements and format specifications.

Deliverables:

* a binding-power table;
* parser functions with manifest entries;
* valid expression snapshots;
* invalid and incomplete-expression snapshots;
* precedence property tests.

Exit criteria:

* all expression fixtures currently accepted in ``tests/core/parser/valid`` have
  a lossless Rowan parse;
* generated source examples reconstruct exactly;
* binding edge cases such as unary/power, comparisons, lambdas, ternaries,
  calls, comprehensions, and assignment expressions are explicit snapshots.

Phase 3: Python statements and blocks
------------------------------------

Implement in increasing dependency order:

1. simple statements and semicolon lists;
2. assignments and annotated assignments;
3. imports;
4. return, raise, assert, global, nonlocal, delete, yield;
5. function and class definitions;
6. parameter and argument lists;
7. if, while, for, with, try;
8. match/case patterns;
9. type aliases and type parameters;
10. decorators and type comments.

Deliverables:

* statement FIRST-set registry;
* block parser with indentation-aware recovery;
* parameter-list state machine;
* target validators;
* Python fixture parity snapshots.

Exit criteria:

* the current valid Python fixture corpus parses losslessly;
* target- and version-sensitive forms produce feature uses rather than changing
  syntax recognition;
* each existing ``invalid_*`` category has either a dedicated recovery test or
  a documented reason it is reached generically.

Phase 4: Enaml overlay
----------------------

Implement:

1. module item dispatch and Python/Enaml module grouping;
2. pragmas;
3. enamldefs, bodies, and single-line items;
4. storage, alias, and const expressions;
5. bindings and extended bindings;
6. Enaml operator expressions and block operators;
7. child definitions and nested bodies;
8. declarative functions and overrides;
9. templates, parameters, instantiations, identifiers, and bindings.

Deliverables:

* Enaml-specific node kinds;
* soft-keyword dispatch isolated from Python identifier use;
* body parser inventory for each legal item set;
* operator adjacency diagnostics for ``::`` and ``=>``;
* all valid Enaml fixture snapshots.

Exit criteria:

* all valid Enaml fixtures parse losslessly;
* ``<<``, ``>>``, ``::``, ``:=``, ``=`` and ``=>`` are correct in both Python
  expression and Enaml binding contexts;
* nested child and template bodies recover at the nearest ``DEDENT``.

Phase 5: diagnostics and invalid PEG rules
------------------------------------------

Port the 54 current ``invalid_*`` rules as categorized recovery behavior.  Do
not port each immediately as an independent parser branch if two rules reach the
same synchronization behavior.

Deliverables:

* an invalid-rule manifest with PEG rule, Rust diagnostic, and synchronization;
* parity tests for diagnostic ranges and categories;
* stable parser states for malformed edits common in an editor:
  missing delimiters, colons, indentation, arguments, operators, and names.

Exit criteria:

* a malformed fixture never loops;
* each fixture reaches a bounded synchronization token;
* diagnostic ranges point into the smallest stable affected construct;
* all source remains in the Rowan tree.

Phase 6: Python feature versioning and 3.15
------------------------------------------

Implement generic feature-use tracking before each individual feature.

First add:

* lazy imports;
* starred list/set/generator comprehensions;
* double-starred dictionary comprehensions.

Then verify the existing gates for:

* 3.8 assignment expressions and positional-only parameters;
* 3.9 generic decorators and parenthesized context managers;
* 3.10 pattern matching;
* 3.11 exception groups;
* 3.12 type aliases and type parameters;
* 3.14 unparenthesized exception lists and t-strings;
* 3.15 lazy imports and comprehension unpacking.

Deliverables:

* a target-version configuration API;
* feature IDs and minimum-version table;
* diagnostics independent of AST construction;
* parser snapshots that are identical across target versions.

Exit criteria:

* changing the target version never changes Rowan recognition;
* only diagnostic and lowering results change;
* the Python 3.15 additions match the worked examples in this document.

Phase 7: semantic lowering
--------------------------

Build lowering only after syntax behavior is stable.

Deliverables:

* optional Python AST-compatible lowering where needed;
* Enaml semantic AST lowering;
* operator block synthetic-function construction;
* template and enamldef validation;
* target-context validation;
* literal decoding;
* runtime-version field adaptation.

Exit criteria:

* semantic lowering does not alter Rowan text or range;
* valid runtime-AST comparison tests continue to pass where a corresponding
  AST is part of the project's requirements;
* semantic errors can be reported without discarding syntax nodes.

Phase 8: LSP integration
-----------------------

Integrate in small feature increments:

1. document parse and reparse;
2. syntax diagnostics;
3. version diagnostics;
4. document symbols;
5. folding ranges;
6. formatting anchors;
7. completion-sensitive parsing;
8. rename and reference scopes.

Deliverables:

* immutable syntax snapshots;
* document version/race handling;
* a stable public syntax API;
* incremental parse reuse only after exact-match performance evidence.

Exit criteria:

* edits cannot race stale diagnostic results;
* incomplete documents retain useful syntax;
* core operations work on source with errors;
* benchmarks establish acceptable parse and allocation behavior on large Enaml
  files.

Definition of done
==================

The reusable lexer and parser are complete enough to support the LSP when:

* the lexer is the only lexical implementation;
* lexing and Rowan parsing both reconstruct source exactly;
* every PEG rule is classified in the manifest;
* all expression precedence is data-driven and special cases are documented;
* all indentation and soft-keyword behavior is explicit;
* current Python and Enaml valid fixtures parse;
* invalid input produces stable, lossless trees;
* Python target versions create diagnostics without changing syntax shape;
* the Python 3.15 lazy-import and comprehension cases satisfy their worked
  examples;
* semantic lowering and diagnostics consume Rowan rather than mutating parser
  events;
* the grammar-diff CI protocol identifies required parser updates for a future
  PEG change.

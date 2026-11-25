.. _lsp_parser_grammar_maintenance:

=====================================
Maintaining the Enaml LSP PEG mapping
=====================================

This note defines the reviewable update process between
``enaml/core/parser/enaml.gram`` and the Rust parser.  It complements the
:ref:`lsp_parser_architecture`, while the :ref:`lsp_parser_python_315` note
demonstrates the process on concrete grammar additions.

Human-readable grammar update decision tree
==========================================

When a PEG diff is received, follow this tree in order.  A maintainer should not
need to infer a mapping by reading generated parser code.

Start at the changed rule
-------------------------

1. Is the rule gone?

   a. Find all manifest entries that name it.
   b. Search parser entry points, syntax kinds, recovery branches, and tests.
   c. Remove or deprecate them only after all references are accounted for.
   d. Add a regression test that proves stale syntax is rejected or preserved
      only as the grammar's new invalid form.

2. Is the changed name prefixed by ``invalid_``?

   a. Classify it as ``recovery``.
   b. Do not add it to valid FIRST-set dispatch as a normal node.
   c. Extract the diagnostic message and condition.
   d. Derive a synchronization set from the rule's valid counterpart.
   e. Add an invalid snapshot and an edit/reparse stability test.

3. Is the changed code only inside a semantic action, ``check_version``, or a
   host-runtime conditional?

   a. Classify it as ``semantic`` or version metadata.
   b. Determine whether lowering, semantic validation, or feature diagnostics
      consume it.
   c. Do not create a new parser branch unless the action gates recognition.

4. Does the rule introduce or remove a literal token spelling, lexer mode, or
   special token family?

   a. Update the Logos token enum or mode.
   b. Reconcile significant tokens with attached trivia.
   c. Update the token/syntax-kind conversion.
   d. Add exact lexing and round-trip tests.

5. Does the rule begin in the expression section?

   a. Is it a direct left recursion of the form ``A OP B | base``?

      i. Classify it as ``pratt-infix``.
      ii. Assign its relative precedence from neighboring PEG levels.
      iii. Determine associativity from recursion and semantic action.
      iv. Determine whether the result is a chain.
      v. Add mixed-precedence and associativity tests.

   b. Is it a direct left recursion consisting of a suffix on ``A``?

      i. Classify it as ``pratt-postfix``.
      ii. Add it to the postfix loop.
      iii. Define whether the suffix can repeat and its terminator.

   c. Is it a prefix token followed by the same/tighter rule?

      i. Classify it as ``pratt-prefix``.
      ii. Add a prefix parselet.
      iii. Check the PEG distinction between ordinary and special prefix use.

   d. Is it a conditional, lambda, yield, target, comprehension, named
      expression, grouping, display, or interpolation construct?

      i. Classify it as ``pratt-special``.
      ii. Parse its fixed syntax recursively.
      iii. Delegate ordinary operands to the Pratt engine.
      iv. Add context and malformed-form tests.

6. Is the rule structural?

   a. Classify it as ``recursive-descent``.
   b. Compute FIRST sets for all alternatives.
   c. Add the smallest bounded lookahead that resolves overlaps.
   d. Observe alternative order and PEG cuts.
   e. Derive terminators and block boundaries.
   f. Add a Rowan node, or document why it maps to an existing node.
   g. Add recovery at the production boundary.

7. Is the rule mainly repetition or a separated list?

   a. Classify it as ``list``.
   b. Select or configure a list helper.
   c. Encode trailing-separator policy.
   d. Encode star/double-star ordering.
   e. Add empty, singleton, multiple, trailing-separator, and malformed
      variants.

8. Does the rule use a contextual keyword?

   a. Keep the lexed token identifier-like unless it is a hard keyword.
   b. Add text-aware FIRST-set dispatch.
   c. Add ordinary-identifier tests for the same spelling.
   d. Check that completion and symbol lookup do not accidentally treat the
      spelling as reserved globally.

9. Does the rule gate on a version?

   a. Recognize the syntax unconditionally for the newest grammar.
   b. Emit a feature use with a minimum version.
   c. Add diagnostics for one version below and at the minimum.
   d. Keep older-runtime AST adaptation in lowering.

10. For every branch, finish the update protocol.

    a. Update the manifest.
    b. Add valid and invalid parser snapshots.
    c. Assert source round-tripping.
    d. Assert precedence or dispatch-specific invariants where relevant.
    e. Run PEG differential tests for a corpus containing the new syntax.
    f. Update provenance with the PEG revision and checksum.

Decision questions that block implementation
--------------------------------------------

Stop and make an explicit decision if the PEG diff does not answer:

* whether two operators share precedence;
* whether a chain is flattened or nested semantically;
* whether a soft keyword remains usable as an identifier;
* whether a comma or newline terminates a list;
* whether a new body is one-line or indentation-sensitive;
* whether a version condition changes recognition or only AST/lowering;
* whether a PEG invalid rule is diagnostic-only or an intended accepted legacy
  form;
* which Rowan parent owns leading trivia at the edited boundary.

These questions should be recorded in the manifest, not resolved differently in
several parser functions.

Rule mapping manifest
=====================

The repository contains a machine-checkable YAML specification for every PEG
rule under ``parser_migration/rules/``.  The directory is generated from the
grammar but its ``migration`` sections are reviewable decisions.  For example,
``comparison.yaml`` records the PEG source, extracted evidence, classification,
Rowan nodes, Pratt strategy, PyO3 conversion route, recovery sets, and tests.

The specifications are not generated parser code.  They are the reviewable
contract between the PEG and Rust implementations.  The supported commands are:

.. code-block:: console

   python parser_migration/scripts/generate_rule_specs.py
   python parser_migration/scripts/generate_rule_specs.py --check
   python parser_migration/scripts/check_rule_specs.py
   python parser_migration/scripts/check_rule_specs.py --strict

The non-strict checker validates generated evidence and schema completeness.
The strict mode additionally requires every rule to have a confirmed migration
decision.  A CI check should:

1. enumerate the top-level PEG rules;
2. require every public PEG rule to appear in the manifest;
3. reject removed PEG names still referenced as active;
4. verify that every parser or syntax kind named in the manifest exists;
5. permit only the documented exception list for helper/internal PEG rules;
6. include the upstream Python grammar source and hash used for the vendor
   update.

Testing and differential strategy
=================================

Test layers
-----------

Use four distinct layers:

1. Lexer reconstruction tests.
2. Rowan snapshot and round-trip tests.
3. Parser-versus-PEG differential tests.
4. PyO3 AST conversion and LSP behavior tests.

Do not combine them into one broad assertion.  A syntax failure should not be
indistinguishable from a lexer or AST-lowering failure.

Parser snapshots should include:

* token kinds;
* node kinds;
* ranges or a stable offset view;
* exact reconstructed source;
* diagnostics and ranges.

Differential acceptance
-----------------------

For every valid PEG fixture:

* the PEG parser must accept it;
* the Rust parser must have no fatal syntax diagnostic;
* the Rust parser must reconstruct the source;
* lower-level semantic expectations are compared only when lowering is in
  scope.

For every invalid fixture:

* the Rust parser may differ in message wording initially;
* it must preserve source and terminate;
* it must identify the same syntactic category and smallest practical range;
* new invalid rules require a Rust test before a grammar-sync change is merged.

Grammar-update CI
-----------------

Whenever ``enaml.gram`` changes, CI should:

1. parse rule names and alternatives;
2. compare them with the previous checked-in grammar snapshot or base commit;
3. fail if the changed rule has no manifest update;
4. fail if a new precedence operator lacks a binding-power entry;
5. fail if a new terminal lacks a Logos/parser-token mapping;
6. run valid and invalid fixtures associated with the changed rules;
7. emit a short report grouped by the classification table.

A grammar update is incomplete if it only changes test snapshots and generated
Python PEG output.

PEG provenance
==============

The Enaml grammar says that its Python section is vendored, but a vendored
grammar is maintainable only when its source identity is recorded.  Each sync
should record:

* CPython version or development branch;
* upstream commit/tag;
* upstream file path;
* upstream grammar file hash;
* Enaml grammar hash after overlay changes;
* Enaml overlay diff;
* Rust manifest revision;
* intentionally excluded upstream rules.

The upstream sync commit should not mix parser implementation changes with an
unrelated Python grammar refresh unless the update is small enough to review as
one diff.

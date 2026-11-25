PEG rule migration specifications
=================================

``parser_migration`` is the temporary home of the hand-maintenance bridge
between ``enaml/core/parser/enaml.gram`` and the future Rust parser.  It is
intentionally top-level so it can move with the parser crate later without
coupling the documentation to implementation layout.

There is one YAML file per top-level PEG rule under ``rules/``.  Each file has:

* source lines and cryptographic hashes for the complete grammar and that rule;
* automatically extracted PEG alternatives, references, literals, AST
  constructors, and version gates;
* a generated classification suggestion;
* an editable migration section for the Rust parser entry point, Rowan nodes,
  PyO3 conversion route, recovery, and tests.

The files are ordinary YAML with no anchors, multiline scalars, or third-party
tag types.  The generator and checker use only the Python standard library.

Generating the specifications
-----------------------------

Run from the repository root:

.. code-block:: console

   python parser_migration/scripts/generate_rule_specs.py

Generation is deterministic.  Existing migration decisions in a valid file are
preserved.  If the PEG body changed, the decision is retained but ``status`` is
set to ``needs-rereview`` and ``peg.previous_body_sha256`` records the reviewed
grammar body.

To verify generation without modifying files:

.. code-block:: console

   python parser_migration/scripts/generate_rule_specs.py --check

Checking the specifications
---------------------------

Run:

.. code-block:: console

   python parser_migration/scripts/check_rule_specs.py

The checker validates:

* exactly one specification for every current PEG rule;
* no extra, duplicate, or misnamed specifications;
* schema version and allowed classification/status values;
* exact source line spans, body hashes, references, literals, AST constructors,
  version gates, and alternatives;
* source-rule coverage against the current whole-grammar hash;
* Rowan node names against the normative node inventory;
* internal consistency of confirmed Pratt classifications;
* migration decision completeness when a rule is marked ``implemented``.

Use ``--strict`` in future parser migration CI.  In strict mode every rule must
leave ``needs-review`` and ``needs-rereview`` and have its migration fields
confirmed.  This is intentionally not required until migration implementation
starts.

Editing a rule specification
----------------------------

Automated ``peg`` and ``evidence`` fields should not be edited manually.  Edit
only ``migration``:

1. Confirm or replace ``classification.confirmed``.
2. Name the Rust parser function in ``parser.entry``.
3. Set the Pratt strategy and associativity when appropriate.
4. Select Rowan node kinds from
   ``docs/source/developer_notes/lsp_parser_rowan_nodes.rst``.
5. Record FIRST/FOLLOW and recovery sets.
6. Mark the PyO3 AST conversion route as ``direct-python-ast``, ``no-ast``, or a
   narrow documented alternative.
7. Add representative valid and invalid fixture references.
8. Change ``status`` to ``confirmed`` only after the decision has been
   reviewed; change it to ``implemented`` only after code and tests exist.

When a PEG rule is added or changed, run the generator, inspect only the
``needs-review``/``needs-rereview`` files, update ``migration``, and commit both
the grammar and specs in the same change.

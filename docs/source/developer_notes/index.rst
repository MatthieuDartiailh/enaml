.. _developer_notes:

Developer notes
================

These notes are meant to help developers and contributors with regards to some
details of the implementation and coding style of the project.

.. toctree::
   :hidden:

   lsp_parser_architecture
   lsp_parser_grammar_maintenance
   lsp_parser_python_315
   lsp_parser_development_plan

LSP parser design
-----------------

The LSP parser notes specify the design and execution plan for a lossless Rust
parser:

* :doc:`lsp_parser_architecture` covers reuse of the Logos lexer, PEG-to-Pratt
  translation, recursive-descent boundaries, and Rowan construction.
* :doc:`lsp_parser_grammar_maintenance` provides the human-readable decision tree
  for translating future PEG changes.
* :doc:`lsp_parser_python_315` applies the rules to lazy imports and unpacking
  in comprehensions.
* :doc:`lsp_parser_development_plan` defines the phased implementation and
  acceptance criteria.

Python codebase
---------------

The Python codebase currently targets Python 3.6+, strives to follow PEP 8 and
uses Numpy style docstring.


Python C++ bindings
-------------------

The bindings are hand-written and relies on cppy (https://github.com/nucleic/cppy).
Enaml tries to use a reasonably modern C API and to support sub-interpreter,
this has a couple of consequences:

- static variables use is limited to cases that cannot lead to state leakage
  between multiple sub-interpreters. Note that this is currently not heavily
  tested and may require some improvements.
- all the non exported symbol are enclosed in anonymous namespaces
- enaml does not use static types and only dynamical types (note that the
  type slots and related structures are stored in a static variable)
- modules use the multi-phases initialization mechanism as defined in
  PEP 489 -- Multi-phase extension module initialization

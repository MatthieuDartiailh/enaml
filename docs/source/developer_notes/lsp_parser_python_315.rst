.. _lsp_parser_python_315:

=======================================
Python 3.15 PEG-to-parser worked examples
=======================================

This note applies the :ref:`lsp_parser_architecture` and
:ref:`lsp_parser_grammar_maintenance` procedures to the current Python 3.15
additions in the Enaml PEG grammar.

Worked Python 3.15 examples
===========================

The current grammar's explicit Python 3.15 additions are lazy imports and
unpacking in comprehensions.  T-strings are also present in this grammar but are
already classified as a Python 3.14 lexical/syntax feature, so they are not a
3.15 parser change.

Example A: lazy imports
-----------------------

Relevant PEG behavior
~~~~~~~~~~~~~~~~~~~~~

The Python statement dispatch permits ``lazy`` as an import starter.  The import
rules then accept:

.. code-block:: python

   lazy import package
   lazy import package as alias
   lazy from package import name
   lazy from .package import name

The grammar includes a version gate for Python 3.15 and invalid recovery for
misplaced ``lazy`` forms.

Decision-tree application
~~~~~~~~~~~~~~~~~~~~~~~~~

1. The new terminal text ``lazy`` is not a hard keyword.
2. ``simple_stmt`` is already structural, so its change is a FIRST-set update.
3. ``import_name`` and ``import_from`` remain recursive-descent rules.
4. The optional prefix is a Rowan token in ``IMPORT_STMT``.
5. The version action becomes a feature diagnostic.
6. The AST's ``is_lazy`` field belongs only to lowering.
7. The invalid ``from pkg lazy import name`` rule becomes targeted recovery.

Lexer and adapter
~~~~~~~~~~~~~~~~~

The lexer emits ``lazy`` as an identifier-like token with exact text.  No Logos
keyword split is necessary.

Parser dispatch
~~~~~~~~~~~~~~~

The parser recognizes an import if:

.. code-block:: text

   token is import
   OR token is from
   OR token text is lazy AND nth(1) text is import/from

The bounded lookahead is essential.  These remain legal ordinary uses:

.. code-block:: python

   lazy = value
   lazy()
   object.lazy

Rowan shape
~~~~~~~~~~~

For ``lazy from pkg import value``:

.. code-block:: text

   IMPORT_STMT
     IDENT("lazy")        contextual LAZY_KW if desired
     IDENT("from")        contextual FROM_KW
     IMPORT_PATH
       IDENT("pkg")
     IDENT("import")      contextual IMPORT_KW
     IMPORT_NAME_LIST
       IMPORT_NAME
         IDENT("value")
     NEWLINE

No trivia is omitted.  In particular, a comment between ``lazy`` and ``from`` is
attached to the ``from`` token but does not alter the significant-token
lookahead.

Version behavior
~~~~~~~~~~~~~~~~

For a project target below 3.15, retain the full node and emit:

.. code-block:: text

   lazy imports are only supported in Python 3.15 and above

For Python 3.15 or newer, emit no compatibility diagnostic.

Malformed behavior
~~~~~~~~~~~~~~~~~~

For:

.. code-block:: python

   from package lazy import name

parse an ``IMPORT_STMT`` far enough to preserve the complete source and emit the
specific "use 'lazy from ...' instead" diagnostic.  Do not reinterpret the line
as two expression statements.

For an incomplete form such as:

.. code-block:: python

   lazy from package

finish the import node, diagnose the missing ``import``/name list, and synchronize
at newline.

Required tests
~~~~~~~~~~~~~~

At minimum test:

.. code-block:: python

   lazy import x
   lazy import x as y
   lazy import x.y
   lazy from x import y
   lazy from x import y as z
   lazy from . import y
   lazy = x
   lazy()
   lazy.attribute
   from x lazy import y
   lazy from x
   lazy import

Each valid form needs 3.14, 3.15, and no-target diagnostics as applicable, and
the ordinary-identifier forms must be accepted without a lazy-import feature use.

Example B: starred list and set comprehensions
----------------------------------------------

Relevant PEG behavior
~~~~~~~~~~~~~~~~~~~~~

Python 3.15 permits a starred first element in comprehension positions:

.. code-block:: python

   [*items for item in iterable]
   {*items for item in iterable}

The additions are not new Pratt infix or prefix operators.  They add a permitted
``starred_expression`` entry in a selected display/comprehension context.

Decision-tree application
~~~~~~~~~~~~~~~~~~~~~~~~~

1. ``listcomp`` and ``setcomp`` remain structural special alternatives.
2. ``starred_expression`` is parsed in ``ComprehensionElement`` context.
3. Display-versus-comprehension dispatch is determined by following ``for``.
4. The Pratt parser handles ``items`` or a tighter operand after ``*``.
5. The ``py_version`` test becomes a 3.15 feature diagnostic.
6. The old invalid production remains a diagnostic explanation for targets
   before 3.15.

Display parser
~~~~~~~~~~~~~~

After an opening bracket:

1. parse one element in ``ComprehensionElement`` mode;
2. inspect the next significant token;
3. if it is ``for``, parse one or more ``for_if_clause`` entries and close a
   comprehension node;
4. otherwise, parse ordinary separated display elements;
5. never reinterpret a comma-separated list as a comprehension.

Conceptual Rowan result:

.. code-block:: text

   LIST_COMP_EXPR
     L_BRACKET
     STARRED_EXPR
       STAR
       NAME("items")
     FOR_CLAUSE
       FOR_KW
       NAME("item")
       IN_KW
       NAME("iterable")
     R_BRACKET

The ``STARRED_EXPR`` node is part of the concrete syntax even if a lowering
pass chooses an existing runtime AST representation.

Precedence test
~~~~~~~~~~~~~~~

This:

.. code-block:: python

   [*head + tail for item in items]

must associate ``+`` inside the starred operand:

.. code-block:: text

   STARRED_EXPR
     STAR
     BINARY_EXPR(head + tail)
   FOR_CLAUSE ...

The expression operand must stop before the contextual ``for`` token.

Example C: starred generator comprehensions
--------------------------------------------

Python 3.15 adds:

.. code-block:: python

   (*items for item in iterable)

The parenthesized display parser must distinguish:

* grouping: ``(items)``
* tuple: ``(items,)``
* generator comprehension: ``(items for item in iterable)``
* starred generator comprehension: ``(*items for item in iterable)``

The grammar update therefore changes the generator-comprehension element entry,
not ``primary`` precedence.  Reuse the same ``ComprehensionElement`` parser but
retain a ``GENERATOR_EXPR`` Rowan node.

Recovery tests should include:

.. code-block:: python

   (*items for item in)
   (*items for item iterable)
   (*items for item in iterable
   (*items,)

The last form remains a tuple display, not an invalid comprehension.

Example D: double-starred dictionary comprehensions
----------------------------------------------------

Python 3.15 adds:

.. code-block:: python

   {**mapping for item in iterable}

This grammar branch has the following shape:

.. code-block:: text

   LBRACE DOUBLE_STAR bitwise_or for_if_clauses RBRACE

The braced display dispatcher therefore needs a four-way distinction:

1. empty dictionary/set;
2. dictionary entry or double-star dictionary display;
3. set display;
4. dictionary/set comprehension.

After ``**``:

1. parse ``bitwise_or`` in the PEG-specified restricted context;
2. look for ``for``;
3. finish a ``DICT_COMP_EXPR`` if found;
4. otherwise continue a normal dictionary display;
5. attach the 3.15 feature diagnostic only to the comprehension form.

The concrete tree must retain:

.. code-block:: text

   DICT_COMP_EXPR
     L_BRACE
     DICT_UNPACK
       DOUBLE_STAR
       EXPR
     FOR_CLAUSE
     R_BRACE

Do not lower it into a synthetic key/value source pair.  A runtime AST may still
use ``key = expression`` and ``value = None`` internally.

Common 3.15 acceptance cases
----------------------------

All four forms must:

* reconstruct exactly from Rowan;
* produce no syntax error on Python 3.15 or an unspecified latest target;
* produce one version feature diagnostic below 3.15;
* produce the expected lowering result in the corresponding target runtime;
* recover independently if the element, ``for``, target, ``in``, iterable, or
  closing delimiter is missing;
* stop the Pratt operand before the contextual ``for`` token.

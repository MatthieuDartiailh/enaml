.. _lsp_parser_architecture:

==============================================
Enaml LSP Parser: PEG to Pratt and Rowan Guide
==============================================

Status and scope
================

This document is an implementation and maintenance specification.  It describes
how to build a lossless Rust parser for the Enaml language server from the
reference PEG grammar in ``enaml/core/parser/enaml.gram``.  The intended concrete
syntax tree is a Rowan tree.

The reference grammar has three materially different parts:

* the Enaml-specific grammar, at the beginning of the file;
* a vendored Python grammar, following the Enaml grammar;
* ``invalid_*`` productions that recognize malformed input to produce targeted
  diagnostics.

Those parts are a specification, not a single parser algorithm.  The proposed
parser uses:

* an existing Logos-compatible lexer;
* a Pratt engine for Python expression precedence;
* recursive-descent entry points for statements, declarations, blocks,
  patterns, parameters, comprehensions, imports, and other structural syntax;
* Rowan events as the syntax-tree construction mechanism;
* lowering and semantic validation passes after syntax parsing.

The existing PEG implementation remains the initial oracle for accepted syntax,
diagnostics, and language-version behavior.  It is not intended to be generated
from, embedded in, or copied mechanically by the Rust parser.

Can the existing Logos lexer be reused?
=======================================

Yes, with a narrow adapter between the Logos output and the Rowan/event parser.
Reusing the lexer is preferable to implementing lexical Python rules a second
time.

The parser only needs a sequence of already-classified semantic tokens and a
lossless way to emit their associated trivia.  It must not reimplement Python's
string, indentation, line continuation, or interpolation lexing.

Required token contract
-----------------------

The Logos lexer is reusable if its public stream satisfies all of these
conditions:

1. Every input byte is represented by either a semantic token, a trivia token,
   or an explicit lexer-error token.
2. Token text and offsets are retained exactly.
3. The semantic stream contains Python ``NEWLINE``, ``INDENT``, and ``DEDENT``
   tokens, when those tokens are structural rather than trivia.
4. String modes expose f-string and t-string start, middle, end, and
   interpolation tokens in the same nested fashion as the PEG grammar expects.
5. Comments, spaces, tabs, and non-significant line endings can be preserved as
   trivia.
6. Keywords that are contextual in Python or Enaml can be distinguished by text
   at parse time.  They may remain identifier-like tokens in the lexer.
7. Each compound operator is a single semantic token where the grammar treats it
   as one operator, for example ``//``, ``**``, ``:=``, ``<<=``, ``->``, and
   ``...``.
8. EOF also carries any trailing trivia.
9. Lexing errors have a stable range and kind and do not make the parser loop
   without making progress.

If any one of these conditions is currently absent, fix or extend the lexer
adapter rather than add a second lexical path to the parser.

Trivia attachment model
-----------------------

Suppose the lexer produces:

.. code-block:: text

   Token {
       kind: SemanticKind,
       text_range: Range<usize>,
       leading_trivia: Vec<Trivia>,
   }

where the semantic token itself and every trivia item retain exact source
ranges.  The parser adapter should present only semantic tokens to lookahead,
while consuming the token's leading trivia when that semantic token is emitted:

.. code-block:: rust

   pub struct SpannedToken {
       pub kind: TokenKind,
       pub range: TextRange,
       pub leading_trivia: Box<[Trivia]>,
   }

   fn bump(&mut self) {
       let token = self.current_token();

       for trivia in &token.leading_trivia {
           self.events.push(Event::Token {
               kind: trivia.into_syntax_kind(),
               text: trivia.text,
           });
       }

       self.events.push(Event::Token {
           kind: token.kind.into(),
           text: token.text,
       });
       self.cursor += 1;
   }

This model permits inexpensive lookahead without making comments or whitespace
visible to grammar dispatch.  It also preserves the original order in Rowan.

The following rules govern the model:

* Attach non-significant trivia to the next semantic token.
* Treat ``NEWLINE``, ``INDENT``, and ``DEDENT`` as semantic tokens when the PEG
  parser can consume or look ahead to them.
* Keep the final trivia on EOF.  The EOF token is not necessarily present in
  Rowan, but its trivia is emitted at the root.
* Do not synthesize token text.  The adapter must emit the exact lexer slice.
* Do not attach the same trivia to both a preceding and a following semantic
  token.
* Do not let expression lookahead cross a significant newline unless the
  selected PEG rule permits implicit continuation.
* Emit lexer errors as dedicated tokens and continue at a known source position.
* A parser checkpoint must account for semantic tokens, not trivia tokens.

The parser's public cursor therefore has two views:

.. code-block:: text

   significant cursor: current(), nth(), at(), eat()
   lossless output:     bump() emits leading trivia, then the semantic token

Two subtle ownership decisions must be frozen by tests:

* A leading comment on a declaration is a child of the syntax node containing
  that declaration's first token, because its trivia is emitted when that first
  token is consumed.
* An isolated comment after a completed declaration is attached to the following
  semantic token, which may be a ``DEDENT``, another declaration, or EOF.
  Consumers must not assume that comments denote semantic parent-child
  relationships.

If a future lexer instead emits a flat token stream with trivia tokens, the
adapter can still construct the same parser view.  Conversely, if the current
lexer already emits a ``SpannedToken``-like object, its attachment should be
used directly.  The parser must not maintain a separate trivia scanner.

Compatibility checklist for the lexer
-------------------------------------

Before implementing parser work, add a compatibility test suite that verifies:

* exact offsets and exact reconstruction for Unicode input;
* spaces, tabs, comments, blank lines, form feeds, and CRLF;
* implicit continuation inside parentheses, brackets, and braces;
* significant newlines at statement boundaries;
* balanced ``INDENT`` and ``DEDENT`` generation;
* parenthesized and unparenthesized f-string/t-string replacements;
* nesting of replacement fields and format specifications;
* backslash continuations;
* all PEG soft keywords as identifiers in otherwise valid positions;
* every compound operator;
* malformed string and interpolation modes;
* trailing trivia at EOF.

Parser work should proceed only after these tests can assert:

.. code-block:: text

   concatenate(token.text for token in lexed_output) == original_input

This is a separate invariant from Rowan round-tripping and catches lexer loss
before parser development makes the cause ambiguous.

Parser architecture
===================

The proposed crate layering is:

.. code-block:: text

   enaml-lexer         existing Logos lexer and trivia attachment
   enaml-syntax        TokenKind, SyntaxKind, Rowan aliases
   enaml-parser        token adapter, event sink, Pratt and recursive descent
   enaml-syntax-bridge lossless token-to-Rowan adapter
   enaml-lower         optional semantic Python/Enaml AST lowering
   enaml-diagnostics   syntax and feature-version diagnostics
   enaml-lsp           LSP document state and feature providers

If all implementation is initially in one crate, preserve those module
boundaries.  The important dependency direction is:

.. code-block:: text

   lexer -> syntax kinds -> parser -> Rowan
                               |
                               +-> lowering -> diagnostics

The lexer must not depend on parser state, and semantic lowering must not happen
inside Pratt or recursive-descent routines.

PEG information categories
==========================

Every PEG rule contributes one or more of the following:

.. list-table::
   :header-rows: 1
   :widths: 22 42 36

   * - Category
     - Question answered
     - Rust destination
   * - Recognition
     - Which token sequence is legal?
     - Pratt or recursive-descent parser
   * - Precedence
     - How do adjacent expression forms group?
     - Binding-power table or special parselet
   * - Context
     - In which syntactic mode is a sequence legal?
     - Entry-point and parser context enums
   * - Ambiguity/order
     - Which alternative wins on a shared prefix?
     - Explicit dispatch with FIRST/fallback lookahead
   * - Version
     - Which Python version permits the feature?
     - Syntax feature diagnostic
   * - Semantic action
     - Which AST object is created?
     - Lowering pass
   * - Validation
     - Which non-grammar restriction applies?
     - Semantic validation pass
   * - Invalid form
     - How should malformed input be explained?
     - Recovery and diagnostic code
   * - Lexer behavior
     - Which tokenization mode or spelling is required?
     - Logos lexer and compatibility tests

Do not translate a PEG action into a Rowan parser unless it affects recognition
or recovery.  For example, checking that a template identifier is declared is
semantic validation, not syntax.

Rule classification table
=========================

Before implementing a PEG rule, give it exactly one primary class:

.. list-table::
   :header-rows: 1
   :widths: 22 43 35

   * - Class
     - Recognition shape
     - Implementation
   * - ``pratt-infix``
     - Direct left recursion with an intervening operator
     - Infix parselet
   * - ``pratt-prefix``
     - Prefix followed by recursive expression
     - Prefix parselet
   * - ``pratt-postfix``
     - Direct left recursion followed by a postfix suffix
     - Shared postfix loop
   * - ``pratt-special``
     - Expression with custom operands, context, or delimiters
     - Special expression function using Pratt for operands
   * - ``recursive-descent``
     - Statement, declaration, block, pattern, or compound form
     - Ordinary parser function
   * - ``list``
     - Repetition, optional separator, or separated sequence
     - Configured list helper
   * - ``lexer``
     - Token spelling or lexical mode
     - Logos rule/state
   * - ``recovery``
     - Name begins with ``invalid_``
     - Diagnostic branch and synchronization set
   * - ``semantic``
     - Action, AST construction, or validation only
     - Lowering/validation
   * - ``not-in-cst``
     - Recognition helper or compatibility artifact
     - No dedicated Rowan node

Common current examples are:

.. list-table::
   :header-rows: 1
   :widths: 23 22 55

   * - Rule
     - Class
     - Reason
   * - ``sum``
     - ``pratt-infix``
     - Left-recursive ``+`` and ``-`` around a tighter operand
   * - ``term``
     - ``pratt-infix``
     - Left-recursive multiplicative operators
   * - ``factor``
     - ``pratt-prefix``
     - Recursive unary prefix operands
   * - ``power``
     - ``pratt-infix``
     - Right-associative ``**`` with special RHS grammar
   * - ``primary``
     - ``pratt-postfix``
     - Chained attribute, call, and subscription suffixes
   * - ``expression``
     - ``pratt-special``
     - Conditional, lambda, and ordinary-expression alternatives
   * - ``simple_stmt``
     - ``recursive-descent``
     - Ordered statement dispatch
   * - ``template_params``
     - ``list``
     - Separated parameters with a variadic tail
   * - ``invalid_arguments``
     - ``recovery``
     - Recognizes malformed call arguments for diagnostics

General PEG-to-parser translation rules
=======================================

Rule P1: Choose the parser mechanism before the node shape
-----------------------------------------------------------

First decide whether the rule is Pratt, recursive descent, lexical, semantic, or
recovery.  Only then decide the Rowan node.  Several PEG rules may deliberately
map to one syntax node.  For example, ``bitwise_or``, ``sum``, and ``term`` can
all create ``BINARY_EXPR`` while retaining distinct binding powers.

Rule P2: Direct infix left recursion becomes a Pratt parselet
--------------------------------------------------------------

A shape such as:

.. code-block:: text

   A:
       | A '+' B { ... }
       | B

becomes a left-associative infix operator.  If ``A`` has several alternatives
with the same token location in the grammar, they share one precedence unless a
separate rule or action establishes another grouping rule.

For left associativity at precedence ``P``, an implementation may use either:

.. code-block:: text

   consume the infix while infix.left_binding_power >= current_min
   parse RHS with right_binding_power = P + 1

or the inverse convention, provided it is used consistently and covered by
tests.

Rule P3: A left-recursive suffix family becomes one postfix loop
----------------------------------------------------------------

``primary`` is not six separate expression precedence levels:

.. code-block:: text

   primary:
       | primary '.' NAME
       | primary genexp
       | primary '(' arguments? ')'
       | primary '[' slices ']'
       | atom

It is a postfix loop over attribute access, direct generator-call arguments,
normal calls, and subscriptions.  The same rule applies to ``dotted_name``,
``dec_primary``, and ``t_primary``.

A new direct left-recursive suffix added to ``primary`` requires:

1. one postfix-loop branch;
2. one Rowan node kind or a documented reuse;
3. its accepted terminators and recovery behavior;
4. a test with multiple chained suffixes.

Rule P4: Prefix recursion and right recursion are not interchangeable
---------------------------------------------------------------------

Unary ``factor`` is right-recursive prefix syntax:

.. code-block:: text

   factor:
       | '+' factor
       | '-' factor
       | '~' factor
       | power

Power is a right-associative infix form:

.. code-block:: text

   power:
       | await_primary '**' factor
       | await_primary

``-2 ** 2`` must remain ``-(2 ** 2)`` and ``2 ** 3 ** 2`` must remain
``2 ** (3 ** 2)``.  The RHS entry point is part of the binding-power definition;
do not casually parse both operands with the same function call.

Rule P5: List actions determine whether a result is a chain
-----------------------------------------------------------

These forms are chains:

.. code-block:: text

   a < b < c
   a and b and c
   a or b or c

They should produce a single comparison or boolean-chain node containing all
operands and operators.  A PEG action collecting values into a list is the
signal to preserve a chain rather than creating a deeply nested binary tree.

Rule P6: Multi-token operators are consumed in one parselet
----------------------------------------------------------

``is not`` and ``not in`` are comparison parselets.  They are not the separate
parse of a prefix ``not`` followed by an infix operator.  Pratt dispatch may use
``nth(1)`` to select the compound comparison token but the Rowan tree must retain
the two original source tokens.

Rule P7: Special expression entry points stay special
------------------------------------------------------

Do not add global Pratt parselets for:

* conditional expressions;
* lambdas;
* assignment expressions in all contexts;
* yield and yield-from;
* starred expressions;
* comprehensions;
* f-string and t-string replacement fields;
* assignment targets.

Use a dedicated parser function for the special form, and call the Pratt engine
for its ordinary expression operands.

Rule P8: Keep all expression contexts explicit
----------------------------------------------

Use a context enum rather than a single ``parse_expr()`` entry point:

.. code-block:: rust

   pub enum ExprContext {
       Ordinary,
       Named,
       Assignment,
       Starred,
       ComprehensionElement,
       Annotation,
       YieldAllowed,
       Target,
       Pattern,
   }

Examples:

* ``:=`` is legal in contexts that enter ``assignment_expression``.
* ``*expr`` is legal in display, call, target, and selected comprehension
  contexts but not everywhere.
* ``yield`` is accepted only in contexts entered by ``yield_expr``.
* ``target`` accepts a restricted primary shape and applies target semantics.
* ``annotation`` may need the version and grammar restrictions of annotation
  syntax rather than ordinary assignment behavior.

An expression parser that accepts more syntax than its PEG entry point causes
hard-to-diagnose grammar drift even if the resulting AST is plausible.

Rule P9: Ordered alternatives become explicit guarded dispatch
---------------------------------------------------------------

PEG alternatives are ordered.  Do not implement ordered alternatives as
unbounded trial-and-rewind parsing.

For a structural rule:

1. derive the FIRST tokens or token texts for each alternative;
2. add bounded lookahead for shared FIRST sets;
3. select one branch;
4. commit after a PEG cut or after a sufficiently unique prefix;
5. recover within that branch.

The grammar's note that ``assignment`` must precede expression statements is an
example where an expression-like prefix is not enough to select the final
alternative.

Rule P10: Optional, repetition, and separators have progress rules
------------------------------------------------------------------

Translate:

.. code-block:: text

   X?   -> parse X only when at FIRST(X)
   X*   -> loop while at FIRST(X)
   X+   -> require one, then loop while at FIRST(X)

Every loop must assert that it consumes a semantic token or emits/reliably
advances over an error.  PEG repetition is not permission to loop on a parser
checkpoint without progress.

Translated list helpers need configuration for:

* opening and closing delimiters;
* item parser;
* separator kind;
* mandatory and optional trailing separator;
* star and double-star elements;
* whether an empty list is legal;
* hard terminators and recovery tokens.

Rule P11: Lookahead tokens must not consume trivia
--------------------------------------------------

Translate PEG:

.. code-block:: text

   &X  -> test current significant token, consume nothing
   !X  -> fail or diagnose if current significant token is X
   ~   -> commit to the chosen alternative

The parser may inspect token text for a soft keyword, but lookahead itself must
not emit events.

Rule P12: Soft keywords remain contextual identifiers
------------------------------------------------------

Examples in the current generated parser include:

.. code-block:: text

   match case type lazy
   enamldef template func alias attr event const pragma

Unless a word is a Python hard keyword in every context, the Logos lexer should
emit it as an identifier-like semantic token.  Parser dispatch checks its text.
The syntax kind can be changed to a contextual keyword token when emitted if
that is useful to Rowan consumers, but this must not prevent ordinary uses as an
identifier.

Rule P13: Indentation and newlines remain semantic
---------------------------------------------------

Rowan must preserve physical trivia, but a parser cannot rely only on attached
whitespace to recognize Python structure.  ``NEWLINE``, ``INDENT``, and
``DEDENT`` remain significant parser tokens.

For a PEG body form, translate:

.. code-block:: text

   NEWLINE INDENT statements DEDENT

to a block function with:

* an explicit ``NEWLINE``;
* an explicit ``INDENT``;
* repeated statement parsing;
* a ``DEDENT``;
* recovery that never crosses an unexpected outer block boundary.

Rule P14: AST actions become lowering, not parser state
-------------------------------------------------------

The following kinds of PEG actions do not belong in event generation:

* constructing ``ast.FunctionDef`` or Enaml AST nodes;
* selecting AST fields for the host Python version;
* creating synthetic Python functions for Enaml block operators;
* validating shadowed template names;
* converting source strings to literal values.

Those actions belong in lowering or semantic validation after Rowan has been
built.  The only exception is when an action changes accepted syntax.  That
condition should be called out explicitly as grammar behavior rather than AST
behavior.

Rule P15: ``sys.version_info`` is an AST compatibility concern
---------------------------------------------------------------

A branch on the interpreter that creates or omits an AST field should not fork
the Rowan grammar.  Build the newest supported Rowan form and perform
host-version-specific lowering only where necessary.

Rule P16: ``py_version`` and ``check_version`` become feature gates
--------------------------------------------------------------------

A feature gate changes diagnostics, not syntax recognition.  The parser should
recognize the newest supported grammar and record a feature use:

.. code-block:: rust

   FeatureUse {
       feature: PythonFeature,
       minimum: PythonVersion,
       range: TextRange,
   }

Diagnostics compare ``minimum`` with the document's configured target version.
This behavior is essential for an LSP, where a document may contain code using a
newer syntax even though the active project targets an older Python release.

Rule P17: ``invalid_*`` rules become diagnostics plus recovery
---------------------------------------------------------------

An ``invalid_*`` rule is not a valid alternative to emit a normal syntax node.
Translate it into:

1. a narrowly matched error pattern;
2. a diagnostic code and message;
3. a synchronization set;
4. a policy for preserving matched tokens.

Prefer the smallest natural boundary:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Parsing context
     - Typical synchronization set
   * - Call or display item
     - Comma or closing delimiter
   * - Parameter item
     - Comma or right parenthesis
   * - Simple statement
     - Semicolon, ``NEWLINE``, or ``DEDENT``
   * - Compound header
     - Colon or ``NEWLINE``
   * - Indented body
     - ``DEDENT`` or an explicit outer-statement boundary
   * - Enaml binding
     - ``NEWLINE`` or ``DEDENT``
   * - Import
     - Semicolon or ``NEWLINE``
   * - Pattern list
     - Comma, colon, or closing delimiter

Avoid synchronization to the next identifier.  It can discard the first
declaration in an Enaml body.

Binding-power baseline
======================

The expression precedence table should be data.  An initial table derived from
the current PEG is, from loose to tight:

.. list-table::
   :header-rows: 1
   :widths: 12 28 32 28

   * - Rank
     - PEG source
     - Forms
     - Implementation
   * - 1
     - ``lambdef``
     - ``lambda ...: ...``
     - special, body expression
   * - 2
     - ``expression``
     - ``x if c else y``
     - right-recursive special form
   * - 3
     - ``disjunction``
     - ``or``
     - boolean chain
   * - 4
     - ``conjunction``
     - ``and``
     - boolean chain
   * - 5
     - ``inversion``
     - ``not``
     - recursive prefix
   * - 6
     - ``comparison``
     - comparisons, ``in``, ``is``
     - comparison chain
   * - 7
     - ``bitwise_or``
     - ``|``
     - left Pratt infix
   * - 8
     - ``bitwise_xor``
     - ``^``
     - left Pratt infix
   * - 9
     - ``bitwise_and``
     - ``&``
     - left Pratt infix
   * - 10
     - ``shift_expr``
     - ``<<``, ``>>``
     - left Pratt infix
   * - 11
     - ``sum``
     - ``+``, ``-``
     - left Pratt infix
   * - 12
     - ``term``
     - ``*``, ``/``, ``//``, ``%``, ``@``
     - left Pratt infix
   * - 13
     - ``factor``
     - unary ``+``, ``-``, ``~``
     - prefix parselet
   * - 14
     - ``power``
     - ``**``
     - right Pratt infix
   * - 15
     - ``await_primary``
     - ``await``
     - contextual prefix
   * - 16
     - ``primary``
     - call, attribute, subscription
     - postfix loop
   * - 17
     - ``atom``
     - identifiers, literals, displays, grouping
     - primary dispatch

The numeric values are not an external API.  Only the relative order and the
special associativity cases are.

Rowan event and error-node strategy
==================================

Parser output model
-------------------

The parser should emit events such as:

.. code-block:: rust

   enum Event {
       Start { kind: SyntaxKind, forward_parent: Option<u32> },
       Token { kind: SyntaxKind, text: Arc<str> },
       Finish,
       Error { diagnostic: Diagnostic },
   }

The forward-parent mechanism is optional but useful when a Pratt loop discovers
that a previously parsed operand is the child of a newly known parent.  The
implementation may instead eagerly open nodes after lookahead.  The choice must
not affect token order.

Recommended Rowan node families
-------------------------------

Use distinct nodes where lowering or LSP navigation depends on the distinction:

.. code-block:: text

   ROOT
   ERROR

   BINARY_EXPR
   UNARY_EXPR
   BOOL_EXPR
   COMPARE_EXPR
   CONDITIONAL_EXPR
   NAMED_EXPR
   LAMBDA_EXPR
   CALL_EXPR
   ATTR_EXPR
   INDEX_EXPR
   STRING_EXPR
   LIST_EXPR
   LIST_COMP_EXPR
   DICT_EXPR
   DICT_COMP_EXPR
   SET_EXPR
   SET_COMP_EXPR
   GENERATOR_EXPR

   IF_STMT
   FOR_STMT
   WITH_STMT
   TRY_STMT
   MATCH_STMT
   FUNCTION_DEF
   CLASS_DEF
   IMPORT_STMT
   ASSIGNMENT

   ENAMLDEF
   CHILD_DEF
   TEMPLATE
   TEMPLATE_INST
   BINDING
   OPERATOR_EXPR
   STORAGE_EXPR
   CONST_EXPR
   ALIAS_EXPR
   DECL_FUNC
   PRAGMA

Punctuation and operators stay as direct tokens or small token-holder nodes.
Names such as ``sum`` or ``term`` need not be Rowan node names.

Incomplete syntax
-----------------

When a required token is missing:

1. emit the missing-token diagnostic;
2. do not synthesize a source token;
3. finish the containing node at the current offset;
4. synchronize only if parsing cannot continue at the selected token;
5. use an ``ERROR`` node only for source tokens that have no valid structural
   parent.

An empty range node is legal for representing a missing child.  This supports
completion and refactoring better than fabricating punctuation text.

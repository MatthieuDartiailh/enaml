.. _lsp_parser_rowan_nodes:

============================
Enaml LSP Rowan node inventory
============================

This document is the normative inventory of concrete Rowan node kinds for the
Rust Enaml parser.  It complements the :ref:`lsp_parser_architecture`: the
architecture explains *how* PEG rules become parser routines, while this
document specifies *which* stable nodes those routines must construct.

The inventory is based on the current ``enaml/core/parser/enaml.gram`` and the
custom nodes in ``enaml/core/enaml_ast.py``.  It is deliberately smaller than
the grammar's rule count.  PEG helpers that only choose between alternatives,
enforce a lookahead, or collect a list can map to an existing node rather than
acquiring a node kind of their own.

Inventory invariants
====================

The following rules are part of the node contract:

1. Every node kind has a stable, non-reused numeric ``SyntaxKind`` value.
2. Every source character belongs to a token in the final Rowan tree.
3. Parentheses, brackets, braces, operators, commas, colons, newlines,
   indentation tokens, comments, and whitespace are not discarded.
4. A PEG helper receives a dedicated node only when LSP navigation, lowering,
   or error recovery benefits from it.
5. Different PEG precedence levels may use one node kind, such as
   ``BINARY_EXPR``.  Operator tokens and binding metadata still determine
   precedence.
6. A Python expression and its assignment-target form can share the expression
   node kind.  A ``TARGET`` wrapper records target context and prevents lowering
   code from inferring context from a source ancestor in an unstable way.
7. Contextual keywords may be represented by ordinary identifier-like token
   kinds.  The enclosing node remains the authority on their role.
8. Missing source is never represented by a fabricated token.  It is represented
   by an absent typed child, a parser diagnostic, or an ``ERROR`` node with
   subsequent synchronization.
9. A ``SyntaxKind`` that is reachable from more than one grammar rule must have
   the same structural contract in all of those locations.
10. Adding a PEG construct requires a node-inventory decision, even when the
    decision is "map it to an existing node and document why."

All kinds below are *non-token* Rowan nodes unless stated otherwise.  The lexer
and syntax-crate token enums are a separate inventory: a row can mention
``NAME``, ``PLUS``, or ``LAZY_KW`` as children without declaring those children
as nodes.

Root, error, and list nodes
===========================

.. list-table::
   :header-rows: 1
   :widths: 24 28 48

   * - Node
     - Created by
     - Structural contract
   * - ``ROOT``
     - Parser entry point
     - The unique outer node.  Owns the leading trivia, complete module body,
       optional EOF-adjacent trivia, and zero or more top-level diagnostics in
       side state.
   * - ``ERROR``
     - Recovery parser
     - One or more source tokens that could not be attached to a valid node.
       It is never used as a substitute for a missing token.
   * - ``MODULE_ITEM_LIST``
     - ``enaml_item*``
     - Ordered top-level Python, Enaml definition, template, and malformed
       module items.  Used only below ``ROOT``.
   * - ``SUITE``
     - ``block`` and indentation-sensitive PEG alternatives
     - Either a simple statement list on one line or ``NEWLINE INDENT``,
       statement-like children, and ``DEDENT``.  A contextual parent identifies
       the legal item kinds.
   * - ``SIMPLE_STMT_LIST``
     - ``simple_stmts``
     - One or more simple statements with optional semicolons and terminating
       ``NEWLINE``.
   * - ``STMT_LIST``
     - ``statements``
     - One or more statement nodes in an indented suite.  This is distinct from
       ``SIMPLE_STMT_LIST`` because its members are line-structured.
   * - ``NAME_LIST``
     - comma-separated names
     - Used for ``global``, ``nonlocal``, template identifiers, or other
       homogeneous name sequences where the punctuation must remain available.
   * - ``EXPR_LIST``
     - PEG list of expressions
     - Ordered expression and separator tokens.  The surrounding node decides
       whether the list semantically creates a tuple, call arguments, a target,
       or a display.
There is intentionally no ``MISSING`` node.  A required child that has no source
is absent from typed accessors and produces a diagnostic.  A fabricated empty
node would make source ownership and green-tree equality ambiguous.

Enaml-specific nodes
====================

Top-level and body nodes
------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin
     - Required children and purpose
   * - ``ENAMLDEF``
     - ``enamldef``
     - Pragmas, contextual ``enamldef``, type name, base name, optional
       identifier, colon, and ``ENAMLDEF_BODY``.
   * - ``ENAMLDEF_BODY``
     - ``enamldef_body``
     - Inline child item or indented child/binding/function/template-inst item
       list.  A leading string is exposed as a ``DOCSTRING`` child.
   * - ``DECL_FUNC``
     - ``decl_funcdef``, ``sync_decl_fundef``
     - Optional ``async``, either ``func NAME`` or the override ``NAME =>``
       spelling, parameters, optional return expression, colon, and Python
       ``SUITE``.
   * - ``TEMPLATE``
     - ``template``
     - Pragmas, contextual ``template``, name, parameter list, colon, and
       ``TEMPLATE_BODY``.
   * - ``TEMPLATE_BODY``
     - ``template_body``
     - Inline item or indented const/child/template-inst item list.  Exposes the
       optional leading ``DOCSTRING``.
   * - ``CHILD_DEF``
     - ``child_def``
     - Type name, optional identifier, two-colon shape where applicable, and
       ``CHILD_DEF_BODY``.
   * - ``CHILD_DEF_BODY``
     - ``child_def_body``
     - Inline child-body item or indented suite.
   * - ``TEMPLATE_INST``
     - ``template_inst``
     - Pragmas, template name, arguments, optional identifiers, second colon,
       and ``TEMPLATE_INST_BODY``.
   * - ``TEMPLATE_INST_BODY``
     - ``template_inst_body``
     - Inline or indented template-inst bindings.  A ``pass`` item may remain
       represented as ``PASS_STMT``.
   * - ``DOCSTRING``
     - leading string in an Enaml body
     - The exact source ``STRING`` or interpolated-string node, but represented
       as a child wrapper so lowering can retrieve it without relying on list
       position.

Pragmas
-------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin
     - Required children and purpose
   * - ``PRAGMA_LIST``
     - ``pragma*`` and ``pragmas``
     - Ordered ``PRAGMA`` children.
   * - ``PRAGMA``
     - ``pragma``
     - Contextual ``pragma``, command name, optional parenthesized argument
       list, and newline.
   * - ``PRAGMA_ARG_LIST``
     - optional pragma arguments
     - Comma-separated ``PRAGMA_ARG`` nodes and punctuation.
   * - ``PRAGMA_ARG``
     - ``pragma_arg``
     - One name, number, or string token.  The exact token kind determines the
       custom AST ``kind`` field.

Declarations and bindings
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin
     - Required children and purpose
   * - ``ALIAS_EXPR``
     - ``alias_expr``
     - Contextual ``alias``, alias name, optional colon, target and dotted
       chain, and newline.
   * - ``CONST_EXPR``
     - ``const_expr``
     - Contextual ``const``, name, optional type reference, and required
       ``OPERATOR_EXPR``.
   * - ``STORAGE_EXPR``
     - ``storage_expr``
     - ``attr`` or ``event``, name, optional type reference, and optional
       ``OPERATOR_EXPR``.
   * - ``BINDING``
     - ``binding``
     - One name and one ``OPERATOR_EXPR``.
   * - ``EX_BINDING``
     - ``ex_binding``
     - A qualified chain and one ``OPERATOR_EXPR``.
   * - ``QUALIFIED_NAME``
     - dotted Enaml chains
     - Name, dot, and name tokens.  Used by alias chains, extended bindings,
       template-inst bindings, and type references where a structured name is
       useful.
   * - ``OPERATOR_EXPR``
     - ``operator_expr``
     - Operator tokens and either an expression child or
       ``OPERATOR_BLOCK``.  The source operators are ``=``, ``<<``, ``>>``,
       ``:=``, ``::``, and block forms.  Consecutive-token spellings remain
       separate even when they lower to ``::``.
   * - ``OPERATOR_BLOCK``
     - block forms of ``operator_expr``
     - The Python ``SUITE`` consumed by ``::`` or ``<<``.  Keeping it separate
       from a Python control-flow suite makes Enaml lowering and recovery
       explicit.
   * - ``TYPE_REF``
     - ``dec_primary``
     - A Python-style dotted type name only; not an arbitrary expression.
   * - ``TEMPLATE_INST_BINDING``
     - ``template_inst_item`` binding alternative
     - Identifier name, optional qualified chain, and ``OPERATOR_EXPR``.

Template helper nodes
---------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin
     - Required children and purpose
   * - ``TEMPLATE_PARAM_LIST``
     - ``template_params``
     - Parentheses are owned by the ``TEMPLATE`` parent; this node owns commas,
       parameter nodes, and the optional star name.
   * - ``TEMPLATE_PARAM``
     - ``template_param``
     - A name plus optional specialization or default expression.  Tokens
       ``:`` and ``=`` distinguish its custom AST form.
   * - ``TEMPLATE_STAR_PARAM``
     - ``'*' NAME`` in template parameters
     - Star token and capturing name.
   * - ``TEMPLATE_ARG_LIST``
     - ``template_args``
     - Ordered arguments and optional star argument.
   * - ``TEMPLATE_ARG``
     - ``template_argument``
     - Exactly one Python expression used as a positional template argument.
   * - ``TEMPLATE_STAR_ARG``
     - star alternative in ``template_args``
     - Star token and one expression.
   * - ``TEMPLATE_ID_LIST``
     - ``template_ids``
     - Comma-separated names and optional star identifier.
   * - ``TEMPLATE_STAR_ID``
     - star alternative in ``template_ids``
     - Star token and name.

Python structural and statement nodes
=====================================

Simple statements
-----------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``EXPR_STMT``
     - expression alternative of ``simple_stmt`` / ``ast.Expr``
     - One expression.  A leading yield is a ``YIELD_EXPR`` child.
   * - ``ASSIGN_STMT``
     - chained ``assignment`` / ``ast.Assign``
     - One or more ``TARGET`` children separated by assignment tokens and one
       RHS expression.
   * - ``ANN_ASSIGN_STMT``
     - annotated ``assignment`` / ``ast.AnnAssign``
     - One target, annotation, optional assignment token and RHS.
   * - ``AUG_ASSIGN_STMT``
     - augmented ``assignment`` / ``ast.AugAssign``
     - One target, one augmented-assignment token, and one RHS expression.
   * - ``RETURN_STMT``
     - ``return_stmt`` / ``ast.Return``
     - Keyword and optional expression.
   * - ``RAISE_STMT``
     - ``raise_stmt`` / ``ast.Raise``
     - Keyword, optional exception expression, and optional ``from`` expression.
   * - ``GLOBAL_STMT``
     - ``global_stmt`` / ``ast.Global``
     - Keyword and ``NAME_LIST``.
   * - ``NONLOCAL_STMT``
     - ``nonlocal_stmt`` / ``ast.Nonlocal``
     - Keyword and ``NAME_LIST``.
   * - ``DEL_STMT``
     - ``del_stmt`` / ``ast.Delete``
     - Keyword and one or more delete targets.
   * - ``ASSERT_STMT``
     - ``assert_stmt`` / ``ast.Assert``
     - Keyword, test expression, and optional message.
   * - ``PASS_STMT``
     - literal ``pass`` / ``ast.Pass``
     - The single keyword.  It is retained in Python and Enaml suites even if
       Enaml AST lowering later filters it.
   * - ``BREAK_STMT``
     - literal ``break`` / ``ast.Break``
     - The single keyword.
   * - ``CONTINUE_STMT``
     - literal ``continue`` / ``ast.Continue``
     - The single keyword.
   * - ``IMPORT_STMT``
     - ``import_name`` / ``ast.Import``
     - Optional contextual ``lazy``, keyword, and ``IMPORT_ALIAS_LIST``.
   * - ``FROM_IMPORT_STMT``
     - ``import_from`` / ``ast.ImportFrom``
     - Optional contextual ``lazy``, relative dots/module path, keyword, and
       import target list or wildcard.
   * - ``IMPORT_ALIAS_LIST``
     - dotted and from-import lists
     - Comma-separated ``IMPORT_ALIAS`` children.
   * - ``IMPORT_ALIAS``
     - ``dotted_as_name`` and ``import_from_as_name``
     - ``DOTTED_NAME`` or name plus optional ``as`` name.
   * - ``DOTTED_NAME``
     - ``dotted_name``
     - Names separated by dots.  It is also used for import source path nodes.
   * - ``TYPE_ALIAS_STMT``
     - ``type_alias`` / ``ast.TypeAlias``
     - Contextual ``type``, name, optional type parameter list, equals, and
       expression.

Definitions, decorators, and parameters
---------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``DECORATOR_LIST``
     - ``decorators``
     - One or more ``DECORATOR`` nodes preceding a definition.
   * - ``DECORATOR``
     - ``decorator``
     - ``@``, dotted/call/named expression, and newline.
   * - ``FUNCTION_DEF``
     - synchronous ``function_def_raw``
     - Decorators may be preceding siblings or a child, then ``def``, name,
       type parameters, parameters, return annotation, type comment, and suite.
   * - ``ASYNC_FUNCTION_DEF``
     - asynchronous ``function_def_raw``
     - Same contract as ``FUNCTION_DEF`` with ``async def``.
   * - ``CLASS_DEF``
     - ``class_def_raw`` / ``ast.ClassDef``
     - Decorators, ``class``, name, type parameters, optional argument list,
       type comment if accepted by the grammar, colon, and suite.
   * - ``PARAM_LIST``
     - ``parameters`` and ``lambda_parameters``
     - Ordered parameter variants, slash separator, bare-star separator,
       commas, and type comments.
   * - ``PARAM``
     - ``param`` / ``ast.arg``
     - Name, optional annotation, optional default, and optional type comment.
   * - ``VARARG_PARAM``
     - star arm of ``star_etc``
     - Star, name, optional annotation, and no default.
   * - ``KWARG_PARAM``
     - double-star arm of ``kwds``
     - Double star, name, and annotation when present.
   * - ``DEFAULT_VALUE``
     - ``default``
     - Equals token and expression.
   * - ``ANNOTATION``
     - ``annotation`` and ``star_annotation``
     - Colon and expression.  The parent identifies ordinary versus starred
       annotation context.
   * - ``TYPE_PARAM_LIST``
     - ``type_params``
     - Brackets and comma-separated ``TYPE_PARAM`` children.
   * - ``TYPE_PARAM``
     - ``type_param`` / ``TypeVar``, ``TypeVarTuple``, ``ParamSpec``
     - Optional star/double-star, name, and optional bound.  Prefix tokens
       determine which runtime AST type to create.
   * - ``TYPE_PARAM_BOUND``
     - ``type_param_bound``
     - Colon and expression.

Compound statements and clauses
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``IF_STMT``
     - first ``if_stmt`` arm
     - Condition, suite, and optional sequence of ``ELIF_CLAUSE`` and/or
       ``ELSE_CLAUSE``.
   * - ``ELIF_CLAUSE``
     - ``elif_stmt``
     - ``elif``, condition, colon, and suite.
   * - ``ELSE_CLAUSE``
     - ``else_block``
     - ``else``, colon, and suite.
   * - ``WHILE_STMT``
     - ``while_stmt`` / ``ast.While``
     - Condition, suite, and optional ``ELSE_CLAUSE``.
   * - ``FOR_STMT``
     - synchronous ``for_stmt`` / ``ast.For``
     - Target, iter expression, type comment, suite, and optional else.
   * - ``ASYNC_FOR_STMT``
     - asynchronous ``for_stmt`` / ``ast.AsyncFor``
     - ``async for`` plus the same children as ``FOR_STMT``.
   * - ``WITH_STMT``
     - synchronous ``with_stmt`` / ``ast.With``
     - Parenthesized or unparenthesized items, type comment, and suite.
   * - ``ASYNC_WITH_STMT``
     - asynchronous ``with_stmt`` / ``ast.AsyncWith``
     - ``async with`` plus the same children as ``WITH_STMT``.
   * - ``WITH_ITEM``
     - ``with_item`` / ``ast.withitem``
     - Context expression and optional target introduced by ``as``.
   * - ``TRY_STMT``
     - ``try_stmt`` / ``ast.Try`` or ``ast.TryStar``
     - Try suite, one or more ordinary or star except clauses, optional else,
       and optional finally.  Mixed except kinds are syntactically preserved and
       diagnosed semantically.
   * - ``EXCEPT_CLAUSE``
     - ``except_block`` / ``ast.ExceptHandler``
     - Optional type expression or 3.14 unparenthesized type list, optional
       ``as`` name, and suite.
   * - ``EXCEPT_STAR_CLAUSE``
     - ``except_star_block``
     - Star token plus type expression/list, optional name, and suite.
   * - ``FINALLY_CLAUSE``
     - ``finally_block``
     - ``finally``, colon, and suite.
   * - ``MATCH_STMT``
     - ``match_stmt`` / ``ast.Match``
     - Subject and one or more ``MATCH_CASE`` children.
   * - ``MATCH_CASE``
     - ``case_block`` / ``ast.match_case``
     - Pattern, optional ``GUARD``, colon, and suite.
   * - ``GUARD``
     - ``guard``
     - Contextual ``if`` and one named expression.

Python expression nodes
=======================

Operators and references
------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``NAME_EXPR``
     - ``atom: NAME`` / ``ast.Name``
     - One identifier token.  Binding context comes from a ``TARGET`` parent
       or lowering mode, not from the lexical token.
   * - ``BINARY_EXPR``
     - ``bitwise_or`` through ``term`` and ``power`` / ``ast.BinOp``
     - Left expression, one operator, and right expression.  Pratt binding
       data determines association; every resulting node is structurally
       identical.
   * - ``UNARY_EXPR``
     - ``factor`` / ``ast.UnaryOp``
     - Unary ``+``, ``-``, or ``~`` and operand.
   * - ``NOT_EXPR``
     - ``inversion`` / ``ast.UnaryOp(Not)``
     - Recursive ``not`` keyword and operand.  Separate from ``UNARY_EXPR`` so
       recursive operator spelling and contexts are typed.
   * - ``BOOL_EXPR``
     - ``disjunction`` and ``conjunction`` / ``ast.BoolOp``
     - At least two operands and repeated ``and`` or ``or`` tokens.  The node
       flattens a same-operator chain into the same form as CPython AST.
   * - ``COMPARE_EXPR``
     - ``comparison`` / ``ast.Compare``
     - Initial operand, one or more comparison operator/token groups, and
       subsequent operands.
   * - ``COMPARE_OP``
     - ``compare_op_bitwise_or_pair``
     - The operator spelling only.  It is required so ``is not`` and ``not in``
       remain two source tokens inside one semantic operation.
   * - ``AWAIT_EXPR``
     - ``await_primary`` / ``ast.Await``
     - ``await`` and primary expression.
   * - ``COND_EXPR``
     - conditional arm of ``expression`` / ``ast.IfExp``
     - Body expression, ``if`` condition, ``else`` expression.
   * - ``NAMED_EXPR``
     - ``assignment_expression`` / ``ast.NamedExpr``
     - Target name, ``:=``, and value expression.
   * - ``LAMBDA_EXPR``
     - ``lambdef`` / ``ast.Lambda``
     - ``lambda``, parameter list, colon, and body expression.
   * - ``ATTR_EXPR``
     - postfix attribute / ``ast.Attribute``
     - Value expression, dot, and name.
   * - ``CALL_EXPR``
     - postfix call / ``ast.Call``
     - Callee, parentheses, optional generator or ``ARG_LIST``.
   * - ``INDEX_EXPR``
     - postfix subscription / ``ast.Subscript``
     - Value expression, brackets, and ``SLICE_LIST``.
   * - ``YIELD_EXPR``
     - ``yield_expr`` / ``ast.Yield``
     - ``yield`` and optional expression list.
   * - ``YIELD_FROM_EXPR``
     - yield-from arm / ``ast.YieldFrom``
     - ``yield``, ``from``, and expression.
   * - ``STARRED_EXPR``
     - ``starred_expression`` / ``ast.Starred``
     - Star and one expression.  Context determines ``Load``, ``Store``, or
       invalid assignment behavior during lowering.
   * - ``GROUP_EXPR``
     - ``group`` and parenthesized patterns
     - Parentheses and the enclosed expression.  It is concrete syntax only;
       lowering usually returns the enclosed AST node while expanding its
       source range to include parentheses.

Primary values and displays
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``LITERAL_EXPR``
     - constant atoms, ``None``, booleans, number, ellipsis
     - One literal token or a parenthesized literal?  The token kind drives
       the custom literal decoder and AST ``Constant`` value.
   * - ``STRING_EXPR``
     - ``strings`` / ``ast.Constant``, ``JoinedStr``, ``TemplateStr``
     - One or more adjacent ``PLAIN_STRING``, ``FSTRING``, or homogeneous
       ``TSTRING`` children.  Mixed ordinary/t-string concatenation remains an
       ``ERROR`` according to PEG.
   * - ``LIST_EXPR``
     - ``list`` / ``ast.List``
     - Brackets and display elements.
   * - ``TUPLE_EXPR``
     - ``tuple`` and expression tuples / ``ast.Tuple``
     - Parentheses/commas and tuple elements.  The exact implicit/explicit
       tuple distinction remains visible in punctuation.
   * - ``SET_EXPR``
     - ``set`` / ``ast.Set``
     - Braces and starred/named expressions.
   * - ``DICT_EXPR``
     - ``dict`` / ``ast.Dict``
     - Braces, ``DICT_ENTRY``, and ``DICT_UNPACK`` children.
   * - ``DICT_ENTRY``
     - ``kvpair``
     - Key expression, colon, and value expression.
   * - ``DICT_UNPACK``
     - double-star ``double_starred_kvpair``
     - Double star and expression.
   * - ``SLICE_LIST``
     - ``slices``
     - Comma-separated ``SLICE`` or expression children.
   * - ``SLICE``
     - ``slice``
     - One optional lower expression, colon, optional upper expression,
       optional second colon, and optional step.
   * - ``DISPLAY_LIST``
     - repeated display elements
     - Comma punctuation and expression/starred-expression children.  It may
       be inlined when the owner node is already the list.

Calls, arguments, comprehensions, and targets
--------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``ARG_LIST``
     - ``arguments`` and ``args``
     - Comma-separated call arguments.  The individual child kind classifies
       the argument.
   * - ``ARG_EXPR``
     - ordinary positional/starred expression argument
     - One expression or ``STARRED_EXPR``.  The source star remains visible.
   * - ``KW_ARG`` / ``ast.keyword``
     - keyword argument
     - Name, equals, and expression.
   * - ``KW_STAR_ARG`` / ``ast.keyword``
     - double-star argument
     - Double-star token and expression.
   * - ``LIST_COMP``
     - ``listcomp`` / ``ast.ListComp``
     - Brackets, element expression, and ``FOR_IF_CLAUSE`` list.
   * - ``SET_COMP``
     - ``setcomp`` / ``ast.SetComp``
     - Braces, element expression, and clauses.
   * - ``GENERATOR_EXPR``
     - ``genexp`` / ``ast.GeneratorExp``
     - Parentheses, element expression, and clauses.
   * - ``DICT_COMP``
     - ``dictcomp`` / ``ast.DictComp``
     - Braces, either ``DICT_ENTRY`` or 3.15 ``DICT_UNPACK``, and clauses.
   * - ``FOR_IF_CLAUSE``
     - ``for_if_clause`` / ``ast.comprehension``
     - Optional ``async``, ``for``, target, ``in``, iterable expression, and
       zero or more filter expressions.
   * - ``COMP_IF``
     - repeated ``if disjunction``
     - ``if`` keyword and filter expression within a ``FOR_IF_CLAUSE``.
   * - ``TARGET``
     - assignment target entry
     - Wraps a name, attribute, subscription, grouped target, list target, tuple
       target, or starred target.  The lowering mode selects ``Store`` or
       ``Del``.
   * - ``TARGET_LIST``
     - ``star_targets``, ``del_targets``
     - Commas and one or more ``TARGET`` children.  Its enclosing statement
       decides tuple versus assignment-chain semantics.
   * - ``STAR_TARGET``
     - ``star_target``
     - Star and nested target.  It is distinct from a load ``STARRED_EXPR``.

String and interpolation nodes
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``PLAIN_STRING``
     - ordinary ``STRING`` token
     - One lexer token including prefix and quotes.  Decoding occurs during
       lowering, not lexing.
   * - ``FSTRING``
     - ``fstring`` / ``ast.JoinedStr``
     - Start and end tokens, zero or more literal middle tokens and
       ``FSTRING_FIELD`` children.
   * - ``TSTRING``
     - ``tstring`` / ``ast.TemplateStr``
     - Start and end tokens, zero or more literal middle tokens and
       ``TSTRING_FIELD`` children.
   * - ``FSTRING_FIELD``
     - ``fstring_replacement_field`` / ``ast.FormattedValue``
     - Braces, expression, optional debug equals, conversion, optional format
       specification, and braces.
   * - ``TSTRING_FIELD``
     - ``tstring_replacement_field`` / ``ast.Interpolation``
     - Same concrete shape as an f-string field, with t-string lowering.
   * - ``FORMAT_CONVERSION``
     - ``fstring_conversion``
     - Exclamation and one conversion-name token.
   * - ``FORMAT_SPEC``
     - ``fstring_full_format_spec`` / joined format value
     - Colon and zero or more literal, f-string-field, or t-string-format
       children.
   * - ``STRING_MIDDLE``
     - f-string/t-string middle token
     - One literal segment.  The parent ``FSTRING`` or ``TSTRING`` selects the
       runtime decoding rules and raw-string state.

Pattern-matching nodes
======================

.. list-table::
   :header-rows: 1
   :widths: 27 31 42

   * - Node
     - PEG origin / AST family
     - Required children and purpose
   * - ``PATTERN``
     - top ``pattern``
     - Uniform wrapper around the selected pattern alternative.  Every
       ``MATCH_CASE``, parent pattern list, and pattern-containing clause owns
       a ``PATTERN`` node so the typed API has one entry point.
   * - ``AS_PATTERN``
     - ``as_pattern`` / ``ast.MatchAs``
     - Pattern, ``as``, and capture target.
   * - ``OR_PATTERN``
     - ``or_pattern`` / ``ast.MatchOr``
     - Two or more closed patterns separated by ``|``.  A single child may
       collapse during lowering.
   * - ``LITERAL_PATTERN``
     - ``literal_pattern`` / ``MatchValue`` or ``MatchSingleton``
     - Signed number, complex literal, concatenated string, ``None``, ``True``,
       or ``False``.
   * - ``CAPTURE_PATTERN``
     - ``capture_pattern`` / ``MatchAs``
     - One capture-name token.
   * - ``WILDCARD_PATTERN``
     - ``wildcard_pattern`` / nameless ``MatchAs``
     - The contextual ``_`` token.
   * - ``VALUE_PATTERN``
     - ``value_pattern`` / ``MatchValue``
     - Qualified dotted name only.
   * - ``GROUP_PATTERN``
     - ``group_pattern``
     - Parentheses and one pattern.  Lowering normally returns the inner
       semantic pattern while preserving the concrete range wrapper.
   * - ``SEQUENCE_PATTERN``
     - ``sequence_pattern`` / ``MatchSequence``
     - Brackets or parentheses and ordered element patterns.
   * - ``STAR_PATTERN``
     - ``star_pattern`` / ``MatchStar``
     - Star and capture/wildcard.
   * - ``MAPPING_PATTERN``
     - ``mapping_pattern`` / ``MatchMapping``
     - Braces, key/value patterns, and optional rest pattern.
   * - ``KEY_VALUE_PATTERN``
     - ``key_value_pattern``
     - Literal/attribute key, colon, and pattern.
   * - ``DOUBLE_STAR_PATTERN``
     - ``double_star_pattern``
     - Double star and capture target.
   * - ``CLASS_PATTERN``
     - ``class_pattern`` / ``MatchClass``
     - Qualified class name, positional patterns, and keyword patterns.
   * - ``KEYWORD_PATTERN``
     - ``keyword_pattern``
     - Attribute name, equals, and pattern.
   * - ``PATTERN_LIST``
     - repeated patterns
     - Comma tokens and pattern children for sequences and class arguments.
   * - ``SUBJECT_EXPR``
     - ``subject_expr``
     - One named expression or an implicit tuple.  The node lets lowering
       reproduce tuple-subject context without adding artificial parentheses.
   * - ``SIGNED_PATTERN_NUMBER``
     - signed and complex-pattern helpers
     - Sign token and numeric literal or a real-plus-imaginary pair.  Lowering
       can be shared with literal expressions but remains syntactically
       constrained here.

Node kind reuse constraints
===========================

The following node kinds are intentionally shared:

* Python and Enaml bodies use ``SUITE`` for indentation mechanics, but
  ``ENAMLDEF_BODY``, ``CHILD_DEF_BODY``, ``TEMPLATE_BODY``, and
  ``OPERATOR_BLOCK`` constrain the child kinds.
* Python ordinary expressions and Enaml embedded Python expressions use the
  expression node inventory unchanged.
* Function and declarative-function parameters use ``PARAM_LIST`` and
  ``PARAM``.  The declarative wrapper supplies its own semantic validation.
* ``QUALIFIED_NAME`` and expression ``ATTR_EXPR`` are not interchangeable:
  ``QUALIFIED_NAME`` accepts only a syntactic name chain, whereas ``ATTR_EXPR``
  may begin with an arbitrary expression and can contain calls or indexing.
* ``STARRED_EXPR`` and ``STAR_TARGET`` share source spellings but have distinct
  lowering contexts and version errors.
* ``LITERAL_PATTERN`` and ``LITERAL_EXPR`` share tokens but must not be one
  node, because pattern lowering is more constrained than expression lowering.

Mandatory wrapper policy
========================

``PATTERN``, ``EXPR_LIST``, ``DISPLAY_LIST``, ``NAME_LIST``, and the
module/body/list wrappers in this inventory are mandatory.  A parser routine
must not inline a listed wrapper merely because a convenient typed accessor is
available.

The same is true for the Enaml body nodes.  Record the node contract in the
grammar manifest and apply it at every call site.  Snapshot tests must show the
chosen wrappers, so future cleanup cannot silently change query navigation.

Node-generation checklist
=========================

For each new ``SyntaxKind``:

1. Add it to the central kind enum with a stable position.
2. Define a short row in this inventory.
3. Add a typed syntax wrapper and typed accessors.
4. Define its allowed children and source order.
5. Define which children are optional, repeated, and error-recoverable.
6. Add at least one full valid snapshot.
7. Add an incomplete version showing all recoverable missing children.
8. Add a lowering arm in the relevant visitor.
9. Add it to the grammar mapping manifest.
10. Document whether it is semantic, concrete-only, or both.

Definition of completeness
==========================

The node inventory is complete for a PEG revision when every grammar rule and
invalid rule can be assigned:

* one node created by that rule;
* an enclosing node whose children the rule populates;
* a token-only helper with no node;
* or an explicit ``not-in-cst`` manifest classification.

No valid language construct may be represented only by ``ERROR``.  Conversely,
the absence of an old construct from this inventory is itself a maintenance
signal when the PEG still references it.

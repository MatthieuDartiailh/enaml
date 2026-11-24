.. _lsp_parser_ast_lowering:

==========================================
Rowan-to-Python-AST conversion for the API
==========================================

This document specifies how a PyO3 extension converts an internal Rowan tree
into the Python and Enaml AST objects consumed by the existing Python API.  It
complements the :ref:`lsp_parser_rowan_nodes` inventory and the
:ref:`lsp_parser_development_plan`.

The parser's Rowan tree is the only source of syntax for conversion.  The
converter must never reparse source text, invoke the Python PEG parser, or
reconstruct child source from a lossy token model.

There are two strictly separate entry points:

* The LSP parses into green and red Rowan syntax and never constructs or
  imports a Python AST.
* The Python extension parses, converts the internal tree inside Rust/PyO3, and
  returns the existing ``ast.AST`` and ``enaml.core.enaml_ast`` objects.

Python never receives a green tree, a red-tree wrapper, a serialized syntax
tree, or a generic intermediate AST.

Goals
=====

Conversion must satisfy:

1. The Enaml compiler, which requires a valid ``enaml.core.enaml_ast.Module``.
2. The Python parser API, which must raise rather than return a partial AST.
3. Python-AST comparison tests, which compare conversion
   with the configured CPython grammar.
4. The LSP, whose requirement is the opposite: consume only green/red syntax
   and syntax diagnostics.
5. Performance, by keeping typed traversal and object construction inside the
   extension rather than crossing Python once per node.

Conversion is strict.  It returns a complete semantic module or raises a Python
exception.  The parser can retain an error-bearing Rowan tree, but that tree is
never converted to a best-effort Python AST for the LSP.

Green tree, red tree, and AST
============================

Rowan terminology
-----------------

The green tree is immutable, position-independent, and contains lossless token
text.  A ``SyntaxNode`` is a red cursor carrying a particular parent and text
offset over a green node.

The Python conversion uses this sequence:

.. code-block:: text

   GreenNode
      |
      | RootLanguage::parse(...)
      v
   SyntaxNode<EnamlLanguage>  (Rust-only red cursor)
      |
      | typed_ast wrappers
      v
   Typed syntax nodes + source ranges
      |
      | Rust/PyO3 conversion visitor
      v
   Python ast.AST + enaml_ast.ASTNode values
      |
      v
   Python sees the same public AST families as today

Do not store an external source offset in a green node or attempt to mutate the
green tree to attach an AST pointer.  Red syntax nodes know their ranges while
traversed.  The LSP retains red syntax for navigation; the PyO3 visitor uses
those ranges transiently while constructing Python objects.

Internal typed syntax layer
---------------------------

Every required node in :ref:`lsp_parser_rowan_nodes` should have a typed wrapper:

.. code-block:: rust

   pub struct BinaryExpr(SyntaxNode);

   impl AstNode for BinaryExpr {
       fn can_cast(kind: SyntaxKind) -> bool {
           kind == SyntaxKind::BINARY_EXPR
       }

       fn cast(node: SyntaxNode) -> Option<Self>;
       fn syntax(&self) -> &SyntaxNode;
   }

   impl BinaryExpr {
       pub fn lhs(&self) -> Option<Expr>;
       pub fn operator(&self) -> Option<SyntaxToken>;
       pub fn rhs(&self) -> Option<Expr>;
   }

These wrappers are Rust implementation details and are never exported to
Python.  They must:

* perform no decoding or AST construction;
* expose exact source children and tokens;
* return ``Option`` for missing children in an incomplete tree;
* return all repeated children in source order;
* never skip ``ERROR`` children silently;
* expose the owning red node for ranges and parent context;
* be cheap, view-like wrappers so conversion does not allocate a second syntax
  model.

PyO3 conversion inputs and outputs
==================================

The Python extension creates an internal conversion session:

.. code-block:: rust

   pub struct AstConversion<'a> {
       source: &'a str,
       file_name: String,
       line_index: LineIndex,
       syntax: SyntaxNode,
       py: Python<'a>,
       python_version: PythonVersion,
   }

The converter runs inside the CPython process that consumes the AST.  Runtime
``sys.version_info`` therefore determines which AST classes and constructor
fields are available.  A newer grammar can be retained in the LSP even on an
older Python, but the Python API conversion fails on a feature unsupported by
that host unless an explicitly configured compatibility AST is requested.

Lowering result
--------------

The conversion returns one owned Python module object:

.. code-block:: rust

   pub fn lower_module(py: Python<'_>, root: SyntaxNode) -> PyResult<Py<PyAny>> {
       let mut conversion = AstConversion::new(py, root);
       conversion.module()
   }

The returned object is an ``enaml.core.enaml_ast.Module`` as today.  Any syntax,
literal, target, version, or Enaml semantic failure becomes a Python exception
before a partial module is returned.

The PyO3 converter should import/cache the required Python constructors once per
call or once in module initialization, then instantiate them directly.  It must
not call Python once to fetch every child, stringify a subtree, serialize a
neutral AST, or expose a syntax-node proxy to Python.

No Rust-owned alternate AST is introduced.  Temporary Rust values are limited
to decoded strings, lists of child Python references, operator tags, locations,
and other values required to call the final Python constructors.

Lowering phases
===============

Use two semantic phases for a strict module:

1. **Structural lowering** directly creates the Python AST objects for a syntax
   subtree, retaining only Rust/PyO3-owned references until the parent
   constructor receives them.
2. **Semantic validation** checks name uniqueness, target legality, version
   gates, template identifier use, and restrictions on Enaml operator blocks.

Literal decoding happens during structural lowering.  The parser-side feature
record used by the LSP is separate; the conversion visitor performs the strict
host-runtime capability check.

Phase boundaries matter because a structurally valid expression may still be an
invalid assignment target or contain an expression prohibited in an Enaml
declarative function.

Dispatch strategy
=================

One root dispatcher
-------------------

Use one exhaustively checked dispatch:

.. code-block:: rust

   fn lower_node(
       &mut self,
       node: SyntaxNode,
       context: LoweringContext,
   ) -> Option<SemanticNode> {
       match node.kind() {
           SyntaxKind::FUNCTION_DEF => self.lower_function(node.cast().unwrap()),
           SyntaxKind::BINARY_EXPR => self.lower_binary(node.cast().unwrap()),
           ...
           _ => self.unexpected_node(node),
       }
   }

Expression, statement, pattern, and Enaml-dispatch entry points should narrow the
allowed node categories before calling the complete dispatcher.  This turns a
bad mapping into a deterministic diagnostic rather than a Rust cast panic.

Context enum
------------

The lowerer needs contextual data even after syntax has parsed:

.. code-block:: rust

   pub enum LoweringContext {
       LoadExpr,
       StoreTarget,
       DelTarget,
       Pattern,
       Annotation,
       EnamlPythonExpression,
       EnamlBlock,
       StrictModule,
   }

Context is not stored by mutating an existing Python ``ast.Name`` after the fact
unless that is the intended compatibility operation.  Instead:

* pass the expected expression context into target lowering;
* recursively apply it to tuple/list/starred targets;
* reject call, yield, lambda, literal, and other non-target forms;
* lower attribute and subscription base expressions in load context;
* lower only the outer name/attribute/subscript as store/delete.

Diagnostics and failures
------------------------

Every conversion failure has:

* stable diagnostic code;
* primary source range;
* optional related syntax ranges;
* category: syntax, version, target legality, semantic Enaml, or host-AST
  capability.

Conversion returns no module if:

* any syntax node is missing required typed children;
* an ``ERROR`` node is encountered in a required subtree;
* a literal cannot be decoded;
* a target is invalid;
* a version-gated feature is below target;
* required semantic validation fails;
* the running host cannot represent a requested Python AST class/field.

The PyO3 layer translates the failure directly to the existing Python exception
shape, including filename and source range.  Any already-created local Python
objects are released by normal Rust/PyO3 ownership unwinding.  Partial AST
objects are not published to Python.

The LSP does not invoke this failure path for ordinary editor diagnostics.  It
reads parser diagnostics and the error-bearing Rowan tree directly.

Location conversion
===================

AST locations must come from source ranges, not from token text being scanned
again.  Maintain a line index with source offsets:

.. code-block:: rust

   struct SourceSpan {
       start: TextSize,
       end: TextSize,
   }

   struct AstLocation {
       lineno: usize,
       col_offset: usize,
       end_lineno: usize,
       end_col_offset: usize,
   }

The Enaml custom AST and CPython AST have different consumers even if they share
field names:

* Enaml ``ASTNode`` fields should match existing parser compatibility.
* Standard Python AST offsets must match ``ast.parse`` for the active semantic
  target.  In particular, Unicode column offsets must be tested against
  CPython's UTF-8-byte behavior rather than assuming character counts.
* Internal diagnostics and syntax maps always use Rowan byte offsets/text sizes.
* Do not derive AST locations from untrimmed trivia ranges.  A node's semantic
  range normally starts with its first non-trivia token and ends at its last
  non-trivia token.

Parenthesized expression ranges may include or omit parentheses depending on the
AST constructor represented.  CPython-style compatibility tests are the source
of truth: store a separate concrete syntax range if the runtime AST range does
not include all delimiters.

Python expression lowering
==========================

Names, literals, and strings
----------------------------

``NAME_EXPR`` lowers to ``ast.Name``.  Its context comes from the explicit
lowering context:

.. code-block:: text

   NAME_EXPR + LoadExpr       -> ast.Name(ctx=Load)
   NAME_EXPR + StoreTarget    -> ast.Name(ctx=Store)
   NAME_EXPR + DelTarget      -> ast.Name(ctx=Del)

``LITERAL_EXPR`` dispatches on its token:

* ``NUMBER``: use the same Python literal decoder as the runtime grammar,
  including imaginary and base-prefixed values;
* ``None``, ``True``, ``False``: construct constants;
* ellipsis: construct ``Ellipsis``.

Never parse the literal by evaluating arbitrary Python code.

Plain adjacent strings are concatenated in source order.  F-string and t-string
families follow the grammar's non-mixing constraints:

* ordinary/f-string concatenation lowers through CPython-equivalent
  ``Constant``/``JoinedStr`` rules;
* t-string-only concatenation lowers through ``TemplateStr`` where supported;
* mixed ordinary and t-string sequences are diagnosed as invalid syntax before
  AST creation;
* raw-string state is attached to the lexer/string node and is used for literal
  segment decoding.

Unary, binary, and chains
-------------------------

``BINARY_EXPR`` maps operator tokens to ``Add``, ``Sub``, ``Mult``, ``Div``,
``FloorDiv``, ``Mod``, ``MatMult``, ``LShift``, ``RShift``, bit operators, and
``Pow`` nodes.  The Pratt tree has already resolved grouping.

``UNARY_EXPR`` maps unary plus, minus, and invert.  ``NOT_EXPR`` maps to
``ast.Not`` recursively.

``BOOL_EXPR``:

1. verify the chain uses one boolean operator kind;
2. lower operands in load context;
3. construct one ``ast.BoolOp`` with all operands;
4. use the range from the first to last operand.

``COMPARE_EXPR``:

1. lower the initial operand;
2. lower every ``COMPARE_OP`` token into an operator object;
3. lower each following operand;
4. construct one ``ast.Compare``.

``is not`` and ``not in`` become one Python operator but retain their two source
tokens in the Rowan-to-semantic map.

Conditional, lambda, named, yield, and await
--------------------------------------------

``COND_EXPR`` lowers body, condition, and else expression separately and
constructs ``ast.IfExp``.  Do not confuse concrete source order with the
CPython AST field order.

``NAMED_EXPR`` lowers its name under store context and the value under load
context.  Version gating for assignment expressions must already have recorded
its feature use.

``LAMBDA_EXPR`` lowers a parameter list and body with the same parameter
machinery as a function definition.

``YIELD_EXPR`` and ``YIELD_FROM_EXPR`` become their respective Python AST nodes.
A statement-level yield is wrapped in ``ast.Expr`` by ``EXPR_STMT`` lowering.

``AWAIT_EXPR`` recursively lowers its primary and constructs ``ast.Await``.

Postfix expressions
-------------------

``ATTR_EXPR`` lowers the base in load context and constructs ``ast.Attribute``
with the attribute spelling.

``CALL_EXPR``:

1. lower the callee;
2. classify children in ``ARG_LIST`` as positional, starred, keyword, or
   double-starred;
3. preserve the runtime ordering rules in the list while separating positional
   and keyword values into CPython AST fields;
4. lower a direct generator argument as one positional ``ast.GeneratorExp``.

``INDEX_EXPR`` lowers the base, then one ``SLICE`` or a tuple/list of slices:

* a single expression remains its expression;
* a single ``SLICE`` creates ``ast.Slice``;
* multiple dimensions create a tuple according to the target Python AST
  version;
* starred dimensions are lowered as starred expressions where permitted.

Displays and comprehensions
---------------------------

``LIST_EXPR``, ``TUPLE_EXPR``, and ``SET_EXPR`` lower child elements in load
context, preserving starred elements.

``DICT_EXPR``:

* lowers a ``DICT_ENTRY`` into one key and one value;
* lowers a ``DICT_UNPACK`` into value plus ``None`` key;
* maintains parallel key/value arrays in source order.

For comprehensions:

1. lower the element or key/value/unpack element;
2. lower each ``FOR_IF_CLAUSE`` in source order;
3. lower the clause target in store context;
4. lower the iterable and filters in load context;
5. set ``is_async`` from the optional ``async`` token;
6. construct the matching ``ast.ListComp``, ``ast.SetComp``,
   ``ast.GeneratorExp``, or ``ast.DictComp``.

The 3.15 unpacking comprehensions remain visible:

* list/set/generator element is a normal ``ast.Starred`` within the AST element;
* double-star dictionary comprehension is lowered using the grammar's
  dictionary-comprehension representation;
* the feature diagnostic is independent of whether the host can instantiate the
  AST.

Assignment target lowering
==========================

``TARGET`` is the only entry point for converting expression-shaped syntax to
assignment or deletion semantics.

Valid targets are:

* ``NAME_EXPR``;
* ``ATTR_EXPR`` whose base can be loaded;
* ``INDEX_EXPR`` whose base and slice can be loaded;
* a tuple/list of targets;
* ``STAR_TARGET`` inside a legal sequence target;
* the same forms wrapped in ``GROUP_EXPR``;
* the grammar's restricted delete-target set.

Lower targets recursively:

.. code-block:: text

   outer TARGET context = Store or Del
   expression base/slice context = Load
   nested sequence child context = same outer Store/Del
   starred target child context = same outer Store/Del

Do not accept every expression that happens to be representable as
``ast.Name``, ``Attribute``, or ``Subscript`` after recursive transformation.
For example, a call target is diagnosed even if its callee would be legal on its
own.

``ASSIGN_STMT`` with multiple equals produces one ``ast.Assign`` with target list
in source order.  ``ANN_ASSIGN_STMT`` and ``AUG_ASSIGN_STMT`` use their own
constructors and do not share the target-chain field shape.

Python statement lowering
=========================

Simple statements
-----------------

``SIMPLE_STMT_LIST`` returns a list, never a synthetic AST node.  Semicolons and
newlines affect source location and navigation only.

``EXPR_STMT`` wraps a lowered expression in ``ast.Expr``.
``PASS_STMT``, ``BREAK_STMT``, and ``CONTINUE_STMT`` construct their
corresponding empty-body nodes.

Return, raise, assert, global, nonlocal, and delete statements map directly
from typed children.  ``DEL_STMT`` uses deletion-target mode.

Imports
-------

Lower import aliases without reparsing dotted text:

* ``DOTTED_NAME`` becomes the separator-normalized dotted spelling;
* an ``as`` child becomes ``asname``;
* relative dots determine ``ImportFrom.level``;
* wildcard import is an ``alias`` with name ``*`` and no ``asname``;
* 3.15 lazy state is copied to the runtime ``ast.Import``/``ast.ImportFrom``
  field only when the host AST version supports it.

Functions and classes
---------------------

Parameter lowering constructs ``ast.arguments``:

1. collect positional parameters without defaults before slash;
2. collect positional parameters with defaults before/through ordinary
   parameters;
3. record variadic positional parameter;
4. collect keyword-only parameters and defaults;
5. record variadic keyword parameter;
6. lower annotations under expression context;
7. apply per-argument type comments.

The exact mapping from slash and star separators should be validated by a
unit-test table.  The lowerer must reject illegal combinations even if the
parser's recovery produced a typed tree.

Function and class type parameters are lowered to ``ast.TypeVar``,
``ast.TypeVarTuple``, and ``ast.ParamSpec``.  This is feature/host-version
dependent.

Definitions:

* flatten a typed ``SUITE`` to statement lists;
* attach decorators in source order;
* lower return annotations and type comments;
* create ``FunctionDef`` or ``AsyncFunctionDef`` according to node kind;
* attach ``type_params`` only on runtimes/representations supporting it.

Control flow
------------

``IF_STMT`` lowers the first condition/suite, then recursively folds
``ELIF_CLAUSE`` children into nested ``If`` nodes in ``orelse``.  A single
``ELSE_CLAUSE`` is lowered as a statement list.

``WHILE_STMT`` and for/with forms lower targets and suites using the statement
lowerer.  Async variants differ only in runtime node class and feature gate.

``TRY_STMT``:

* ordinary ``EXCEPT_CLAUSE`` children populate ``Try.handlers``;
* star clauses select ``TryStar`` where supported;
* mixed ordinary/star clauses produce the PEG-compatible diagnostic and no
  strict AST;
* else and finally are independently optional.

Match statements
----------------

``MATCH_STMT`` lowers a ``SUBJECT_EXPR`` and one ``match_case`` per
``MATCH_CASE``.  Guards lower as ordinary expressions.  Pattern lowering is a
separate dispatch because the resulting AST is ``ast.pattern``, not
``ast.expr``.

String and f-string/t-string lowering
=====================================

Replacement fields
------------------

For every ``FSTRING_FIELD`` or ``TSTRING_FIELD``:

1. lower the expression;
2. lower debug-equals flag if present;
3. decode the conversion name;
4. lower nested ``FORMAT_SPEC`` values;
5. construct ``FormattedValue`` for f-strings or ``Interpolation`` for
   t-strings;
6. construct exact source locations.

Nested fields use the same recursive lowering but must not share mutable
raw-string state.  Raw mode is a property of the owning start token.

Concatenation
-------------

Use a segment flattener:

* merge adjacent constant string segments;
* retain formatted/interpolation values between literals;
* do not discard empty leading, trailing, or adjacent segments if source/AST
  compatibility requires their observable nodes;
* concatenate only after confirming token families are grammar-compatible.

Pattern lowering
================

Patterns have a distinct visitor dispatch:

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Syntax node
     - AST target
   * - ``LITERAL_PATTERN``
     - ``MatchValue`` or ``MatchSingleton``
   * - ``CAPTURE_PATTERN``, ``WILDCARD_PATTERN``
     - ``MatchAs`` with name or ``None``
   * - ``AS_PATTERN``
     - ``MatchAs(pattern, name)``
   * - ``OR_PATTERN``
     - ``MatchOr``, unless one child after PEG collapse
   * - ``VALUE_PATTERN``
     - ``MatchValue`` with qualified load expression
   * - ``GROUP_PATTERN``
     - inner pattern with the concrete source mapping retained
   * - ``SEQUENCE_PATTERN``
     - ``MatchSequence``
   * - ``STAR_PATTERN``
     - ``MatchStar``
   * - ``MAPPING_PATTERN``
     - ``MatchMapping``
   * - ``CLASS_PATTERN``
     - ``MatchClass``

Literal-pattern decoding must enforce the grammar's restrictions; it is not
equivalent to generic expression lowering.  Mapping keys are limited to literal
expressions or qualified attributes.  Captures, wildcards, and repeated names
are validated after or while lowering according to CPython pattern semantics.

Enaml lowering
==============

Module grouping
---------------

``ROOT`` lowering walks ``MODULE_ITEM_LIST`` in source order.  Consecutive
Python statements are grouped into one ``PythonModule`` exactly as
``BaseEnamlParser.create_enaml_module`` does.  Encountering an ``ENAMLDEF`` or
``TEMPLATE`` flushes the current Python chunk.

Top-level pragmas belong to the Enaml module's ``pragmas`` field when the
grammar/compatibility semantics require it.  Pragma-bearing definitions attach
their own pragmas directly.

Do not split Python modules by blank lines or comments.  Splitting is based on
semantic statement nodes.

Custom AST field mapping
------------------------

The PyO3 Enaml converter must provide one explicit conversion for every class
currently defined by ``enaml/core/enaml_ast.py``:

.. list-table::
   :header-rows: 1
   :widths: 30 36 34

   * - Custom AST target
     - Required semantic children
     - Main source node
   * - ``PragmaArg``
     - decoded kind and value
     - ``PRAGMA_ARG``
   * - ``Pragma``
     - command and argument list
     - ``PRAGMA``
   * - ``Module``
     - grouped body and module pragmas
     - ``ROOT``
   * - ``PythonExpression``
     - one Python ``ast.Expression``
     - expression child below an Enaml node
   * - ``PythonModule``
     - one Python ``ast.Module``
     - grouped top-level or operator block
   * - ``EnamlDef``
     - type, base, identifier, docstring, pragmas, body
     - ``ENAMLDEF``
   * - ``ChildDef``
     - type, identifier, body
     - ``CHILD_DEF``
   * - ``ConstExpr``
     - name, type reference, Python expression
     - ``CONST_EXPR``
   * - ``AliasExpr``
     - name, target, dotted chain
     - ``ALIAS_EXPR``
   * - ``FuncDef`` / ``AsyncFuncDef``
     - Python function node and override flag
     - ``DECL_FUNC``
   * - ``OperatorExpr``
     - semantic operator and Python expression/module
     - ``OPERATOR_EXPR``
   * - ``Binding``
     - name and operator expression
     - ``BINDING``
   * - ``ExBinding``
     - name chain and operator expression
     - ``EX_BINDING``
   * - ``StorageExpr``
     - kind, name, type, optional operator
     - ``STORAGE_EXPR``
   * - ``PositionalParameter``
     - name and optional specialization
     - ``TEMPLATE_PARAM``
   * - ``KeywordParameter``
     - name and default
     - ``TEMPLATE_PARAM``
   * - ``TemplateParameters``
     - positional, keyword, and star lists
     - ``TEMPLATE_PARAM_LIST``
   * - ``Template``
     - name, pragmas, parameters, docstring, body
     - ``TEMPLATE``
   * - ``TemplateArguments``
     - ordinary arguments and star argument
     - ``TEMPLATE_ARG_LIST``
   * - ``TemplateIdentifiers``
     - names and star name
     - ``TEMPLATE_ID_LIST``
   * - ``TemplateInst``
     - name, pragmas, arguments, identifiers, body
     - ``TEMPLATE_INST``
   * - ``TemplateInstBinding``
     - name, chain, operator expression
     - ``TEMPLATE_INST_BINDING``

This table is the required PyO3 constructor contract, separate from the
standard Python AST dispatch.  A custom Enaml class addition without an entry
here is a conversion error.

Enaml definitions
-----------------

``ENAMLDEF`` lowers:

* type name and base as strings;
* optional identifier;
* first docstring from ``ENAMLDEF_BODY``;
* pragmas;
* lowerable body children;
* source location.

Filter ``PASS_STMT`` from the custom AST body after it has remained preserved in
Rowan.

``CHILD_DEF`` lowers the type, optional identifier, and recursively lowered
body.  It does not create any Python AST node itself.

Bindings and operators
----------------------

``OPERATOR_EXPR`` has two lowering modes:

* expression operators lower to ``enaml_ast.PythonExpression``;
* block operators lower to ``enaml_ast.PythonModule`` containing the synthetic
  zero-argument function expected by the existing compiler.

The synthetic block function is semantic output.  It must:

* use the body statements lowered from the concrete ``OPERATOR_BLOCK``;
* receive a location spanning the concrete block;
* have the existing synthetic name and empty arguments;
* be validated for constructs forbidden by ``::`` or ``<<``.

The adjacency-sensitive source spellings of ``::`` and ``=>`` are concrete
syntax decisions.  Lowering sees a validated ``OPERATOR_EXPR`` token sequence
and emits the semantic operator string.

``BINDING`` and ``EX_BINDING`` lower the target name/chain and operator AST.
``STORAGE_EXPR`` also lowers its ``attr``/``event`` kind and optional dotted
type reference.  ``CONST_EXPR`` and ``ALIAS_EXPR`` keep their custom node fields.

Declarative functions
---------------------

``DECL_FUNC`` lowers:

* ``func`` form or override ``=>`` form;
* parameters and return type through the Python parameter machinery;
* body to Python statements;
* ``FunctionDef`` or ``AsyncFunctionDef``;
* custom ``is_override`` flag.

Run the declarative-function semantic validation over all lowered body AST
nodes.  Disallowed nested functions, classes, yields, and generator expressions
are diagnosed with the concrete Rowan ranges mapped to the generated AST nodes.

Templates
---------

``TEMPLATE_PARAM`` maps to:

* ``PositionalParameter`` for a bare or specialization form;
* ``KeywordParameter`` for the default-value form.

``TEMPLATE_PARAM_LIST`` constructs custom ``TemplateParameters`` and applies the
validation that a non-default positional parameter cannot follow a default
parameter and that names are unique.

``TEMPLATE`` lowers name, pragmas, parameters, docstring, constants, child
definitions, and template instances.  Validate:

* parameter/const shadowing;
* duplicate const names;
* child/template identifier shadowing.

``TEMPLATE_ARG_LIST`` lowers ordinary arguments and the optional starred
expression.  ``TEMPLATE_ID_LIST`` lowers names and the optional star name.

``TEMPLATE_INST`` lowers arguments, identifiers, pragmas, and all
``TEMPLATE_INST_BINDING`` values.  Run the existing rule that a binding name
must refer to an identifier declared by the instantiation.

Location and transient source ownership
=======================================

During PyO3 conversion, retain the current concrete node on the Rust stack:

.. code-block:: text

   typed red node -> Python AST object or Python list

Synthetic Python objects use the range of their concrete owner:

* one Rowan conditional expression creates one ``IfExp``;
* one ``EXPR_STMT`` wraps one expression AST in ``ast.Expr``;
* one Enaml block operator creates one custom ``PythonModule`` containing a
  synthetic function;
* an implicit tuple expression creates ``ast.Tuple`` from the
  ``EXPR_LIST``/comma-bearing concrete node;
* a leading Enaml ``DOCSTRING`` is both represented in Rowan and used as the
  custom AST docstring, not retained as an ordinary body item.

No syntax-to-AST map crosses the PyO3 boundary.  A long-lived map would expose
neither current Python API behavior nor an LSP feature and would keep Python
objects alive unnecessarily.

Semantic validation passes
==========================

Keep validations out of parser node creation.  Run them after strict structural
lowering:

1. Python version feature validation.
2. Assignment/delete target validation.
3. Match-pattern validation where not guaranteed by the grammar.
4. Enaml declaration identifier uniqueness and shadowing.
5. Template parameter ordering and uniqueness.
6. Template const and identifier shadowing.
7. Template-inst binding identifiers.
8. Enaml operator-block forbidden nodes.
9. Declarative-function forbidden nodes.
10. Runtime AST host-capability checks.

Validation happens while converting its concrete owner, or immediately after a
complete Python subtree has been constructed.  The visitor reports the red
node's range, raises an exception, and discards the partially constructed local
AST objects.

Python version and host AST strategy
====================================

The parser records feature uses for LSP diagnostics:

.. code-block:: rust

   struct FeatureUse {
       feature: PythonFeature,
       minimum: PythonVersion,
       syntax: GreenNodeId,
   }

Examples include lazy imports, match statements, exception groups, generic type
parameters, unparenthesized multi-exception clauses, t-strings, and 3.15
comprehension unpacking.

These feature records remain inside the syntax side.  The PyO3 conversion path
performs a separate strict runtime check:

1. if the running host has the required AST class and fields, construct it;
2. otherwise raise the existing Python version error;
3. adapt known host-version field differences, matching the current PEG
   implementation.

Version adaptation is not syntax adaptation.  Never delete or rewrite Rowan
nodes because the host is old.  The LSP can display 3.15 syntax while a Python
3.14 extension correctly refuses to emit an AST that its runtime cannot
represent.

Performance and reuse
=====================

The normal LSP path consumes Rowan and never enters PyO3 AST conversion.  It must
not cache or request Python objects for hover, completion, symbols, diagnostics,
or reparse.

The Python parser API performs one conversion for one successfully parsed
module.  Performance comes from:

* typed red-tree access with no intermediate generic AST;
* no text serialization or Python syntax wrapper allocation;
* no per-token Python callbacks;
* constructor/class references cached in Rust for the conversion call;
* source slices borrowed while Python objects are constructed;
* child vectors accumulated in Rust and passed to one Python constructor call;
* one traversal for construction plus narrowly scoped semantic validations;
* releasing the Rowan tree after Python has received the complete AST.

AST construction is not incrementally reused.  A Python consumer that edits
source parses and converts again; the LSP independently performs incremental
green/red syntax reuse without carrying Python AST objects.

Testing strategy
================

Typed-lowering unit tests
------------------------

For every node inventory row:

* construct a valid Rowan snapshot;
* lower with no diagnostics;
* assert semantic kind and children;
* assert syntax/AST location mapping;
* convert only through the PyO3 extension and assert the public object type;
* assert invalid/incomplete input raises and exposes no partial AST.

Python AST differential tests
-----------------------------

For Python-only fixtures:

1. parse and lower with the Enaml syntax parser;
2. parse the same source with ``ast.parse`` on the test runtime;
3. compare a stable structural dump including semantic locations;
4. explicitly normalize known host-version-only fields;
5. isolate Unicode locations and t/f-string details in focused tests.

Enaml AST differential tests
----------------------------

For every existing valid Enaml fixture:

* compare old PEG/custom AST and new Rowan lowering structurally;
* preserve source locations;
* compare body filtering of ``pass``;
* compare synthetic operator-block functions;
* compare template and declaration validation warnings/errors.

Invalid/recovery tests
----------------------

For every ``invalid_*`` PEG category:

* confirm the Python extension produces no executable AST;
* confirm the LSP parser terminates and preserves the same Rowan recovery;
* confirm all input is still present in Rowan;
* confirm a single typo does not cause synthetic child cascade.

AST lowering completion checklist
=================================

Green-to-AST conversion is complete when:

1. Every node in :ref:`lsp_parser_rowan_nodes` has a lowerer decision.
2. Every ``enaml_ast.ASTNode`` field is sourced from a documented typed child.
3. Every Python AST family represented by the PEG has a lowering route.
4. AST locations are tested on ASCII and non-ASCII sources.
5. LSP feature diagnostics are independent of host AST availability, while
   Python conversion is explicit about host capability.
6. Invalid input yields parser diagnostics for the LSP and an exception for the
   Python AST API; neither path returns a partial AST.
7. No conversion function reads or reparses raw source beyond literal/token
   decoding.
8. Enaml module grouping and operator-block synthesis match the current
   compiler AST.
9. Semantic validations use Rowan-to-AST mappings for ranges.
10. A grammar-manifest update cannot be accepted without a lowering decision
    for any new semantic node.

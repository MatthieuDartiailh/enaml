# Enaml Atom to Ators Migration Plan

## Implementation status

This plan is persisted for the later ators migration and is not implementation
work for the Rust migration. It remains gated on the upstream ators repository
providing dynamic member creation, public metaclass/member APIs, observer/change
kinds, and a tagged supported release.

This plan starts after the Rust extension migration is stable.

## Runtime and dependency decisions

- Raise Enaml's minimum Python version to 3.14 for the ators transition.
- Ators will be a tagged, published dependency; do not depend on mutable `main`.
- Characterization commit: `815590b71de67b99be27d3ee729df9db9a261bce` (ators
  0.1.0). It is not a production pin.
- Atom will remain available during a deprecation period, then leave Enaml's
  default dependencies. Atom is no longer required for Enaml or ators-only
  models, but installed Atom models must continue to drive Enaml views.

## Concrete ators constraints

- `Ators` corresponds to `Atom`; `AtorsMeta` is currently private at
  `ators._meta.AtorsMeta`.
- `member()` is the Ators member builder. Ators declarations are based on
  Python annotations rather than Atom constructors such as `Str`, `Typed`, or
  `Instance`.
- `Member.metadata` is finalized at class creation. Declarative `d_` tags,
  defaults, and handlers must be configured before `AtorsMeta.__new__`.
- Ators has no Python `Member.clone()` or `add_member` and fixes storage slot
  counts at class creation. This blocks the compiler-generated
  `attr`/`event` path in `enaml/core/compiler_helpers.py`.
- `observe()` and `unobserve()` are free functions; Ators has no instance
  `obj.observe()`, no unobserve-all form, no dotted observation, and no
  `ChangeType`.
- Ators callbacks receive `AtorsChange(object, member_name, oldvalue, newvalue)`.
  Atom callbacks receive a change dictionary or are callable with no arguments.
- Static observers do not exist. Ators deletion and initialization behavior
  differs from Atom and needs explicit normalization.
- Events are write-only assignments in ators, not callable Atom events.
- `NotifyingList` and `NotifyingMap` emit Added/Removed/Replaced/Moved container
  operations rather than Atom container change dictionaries.
- Ators supports weakrefs for classes declared with `enable_weakrefs=True`.
  Enaml should prefer normal weakrefs over `atorsref` for framework objects.

## Required upstream ators work

1. Publicly export `AtorsMeta` and publish a stable documented API.
2. Add a safe `add_member(cls, name, builder)` for use before the first instance.
   It must update descriptors, member-name maps, slot counts, init flags,
   validation, and metadata, and reject live post-instantiation mutation unless
   Ators has a documented overflow-slot mechanism.
3. Expose member cloning/customization and builder-time metadata/default/validator
   access sufficient for `DeclarativeMeta`.
4. Define change kinds and observer identity/token semantics for update, event,
   delete, and create where applicable.
5. Prefer public static-observer and dotted-observation support. If static
   observers are not added, Enaml may use one composed dispatcher per class.
6. Publish a tagged release containing these APIs and all characterization tests.
   Never pin mutable ators `main` in release metadata.

## Enaml compatibility layer

Add a private `enaml.core` model adapter with explicit operations for member
lookup, member enumeration, subscribe, unsubscribe, event emission, and change
normalization.

- The ators adapter uses `get_member`, `get_members`, `ators.observe`,
  `ators.unobserve`, assignment events, and `AtorsChange`.
- The Atom adapter lazily imports Atom and uses its existing `get_member`,
  `observe`, `unobserve`, static-observer, and change-dictionary APIs.
- Atom must never be imported at Enaml startup in an ators-only install.
- Register concrete ators/Atom backends; do not use permissive exception probing
  to decide the model type.

## Preserve reactive Atom models

Refactor `StandardTracer` to ask the model adapter instead of
`isinstance(obj, Atom)`.

- Ators and Atom members both resolve aliases, `getattr`, dotted paths,
  container mutations, and computed expressions through the same traced
  dependency set.
- `SubscriptionObserver` must accept ators' one-argument callback and Atom's
  no-argument callback while retaining weak owner invalidation.
- Preserve `<<`, `:=`, `>>`, `::`, ordinary assignment, events, and teardown.
- Plain Python objects remain readable/writable but are not advertised as
  reactive.
- Test real Atom models, not mocks, in a dedicated Atom compatibility
  environment. The ators-only environment must import and run without Atom.

## Port Enaml-owned types

1. Make `Object(Ators, enable_weakrefs=True, observable=True)`.
2. Port `name`, `_parent`, `_children`, `_flags`, and `destroyed`, while retaining
   parent/child and public property behavior.
3. Add `Object.members`, `get_member`, `observe`, and `unobserve` compatibility
   methods, and track subscriptions for no-argument unobserve and destroy cleanup.
4. Replace Atom `atomref` uses with ordinary weakrefs on Enaml-owned objects.
5. Make `DeclarativeMeta(AtorsMeta)`. Transform `d_` metadata and defaults in
   builder-time metadata before class finalization.
6. Replace Atom static observers with one composed ators dispatcher per readable
   declarative member. Where ators gains static/dotted observers, prefer those
   APIs; otherwise keep dotted and lifecycle subscriptions behind Enaml's
   private adapter.
7. Change `compiler_helpers.add_storage` to build a tagged ators member/event
   and call ators `add_member` before instantiation.
8. Migrate declarations in batches: core/compiler/layout, application/workbench,
   widgets, Qt/docking/scintilla, examples, and benchmarks.
9. Convert Atom `ContainerList` uses to `NotifyingList` only when mutation
   notifications matter. Adapt container operations for existing `Include` and
   tool handlers. Convert dictionaries to `NotifyingMap` only when mutations
   must be observed.
10. Explicitly migrate events, properties, coercion/validation, custom constraint
    members, `set_default`, `ForwardTyped`, and `member.reset` call sites.

The compatibility guarantee is for Atom *models*, not arbitrary Atom subclasses
of Enaml framework classes.

## Package and documentation stages

1. Require ators only after a tagged release supplies the upstream prerequisites.
2. Raise Enaml to `requires-python = ">=3.14"` and align classifiers and CI.
3. Keep Atom in a compatibility extra temporarily; announce deprecation.
4. Move Atom out of default dependencies after the deprecation window. Retain
   the lazy Atom adapter and continue supporting Atom as an optional extra.
5. Update installation, anatomy, syntax, extension-author, and release docs,
   plus examples demonstrating ators-first and Atom-model interoperability.

## Test and acceptance gates

- Characterize ators and Atom for updates, deletion, event, container, alias,
  dotted, weakref, inheritance, metaclass, dynamic member, and default behavior.
- Run ators-only and Atom-interop CI environments.
- Prove `<<`, `:=`, `>>`, `::`, `getattr`, `ContainerList`/`NotifyingList`,
  reset, destroy, and resubscription with real ators and Atom models.
- Verify Enaml imports and compiles with Atom absent.
- Verify Enaml imports and remains reactive when Atom is separately installed.
- Keep no direct Atom import outside the lazy compatibility adapter and explicit
  compatibility tests.
- Ship a tagged ators pin and committed migration capability matrix; never
  release against ators `main`.

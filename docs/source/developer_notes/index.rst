.. _developer_notes:

Developer notes
================

These notes are meant to help developers and contributors with regards to some
details of the implementation and coding style of the project.

Python codebase
---------------

The Python codebase currently targets Python 3.6+, strives to follow PEP 8 and
uses Numpy style docstring.


Python Rust bindings
--------------------

Native Python bindings live in ``crates/enaml-python`` and are built with
PyO3 and Maturin. The workspace can be checked and formatted with:

.. code-block:: console

    cargo fmt --check
    cargo clippy --workspace --all-targets -- -D warnings
    cargo test --workspace
    maturin develop

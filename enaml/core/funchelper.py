# --------------------------------------------------------------------------------------
# Copyright (c) 2026, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# --------------------------------------------------------------------------------------
"""Public interface to the rust accelerated declarative function implementation."""

from enaml._rust import call_func

call_func.__module__ = "enaml.core.funchelper"

__all__ = ["call_func"]

# ------------------------------------------------------------------------------
# Copyright (c) 2026, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The license is in the LICENSE file in the project root.
# ------------------------------------------------------------------------------
"""Weak references to callable Python objects."""

from enaml._rust import CallableRef as _CallableRef


class CallableRef(_CallableRef):
    """A weak callable reference."""

    __module__ = "enaml.callableref"


__all__ = ["CallableRef"]

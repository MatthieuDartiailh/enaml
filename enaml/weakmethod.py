# ------------------------------------------------------------------------------
# Copyright (c) 2026, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The license is in the LICENSE file in the project root.
# ------------------------------------------------------------------------------
"""Weak references to bound Python methods."""

from weakref import WeakKeyDictionary

from enaml._rust import WeakMethod as _WeakMethod


class WeakMethod(_WeakMethod):
    """A weak reference to a bound method which caches equivalent methods."""

    __module__ = "enaml.weakmethod"
    _cache = WeakKeyDictionary()

    def __new__(cls, *args, **kwargs):
        if kwargs:
            raise TypeError("WeakMethod() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("WeakMethod() takes 1 argument")
        method = args[0]
        if getattr(method, "__self__", None) is None:
            raise TypeError("WeakMethod() argument must be a MethodType")
        owner = getattr(method, "__self__", None)
        function = getattr(method, "__func__", None)
        if owner is None or function is None:
            return super().__new__(cls, method)

        methods = cls._cache.get(owner)
        if methods is not None:
            cached = methods.get(function)
            if cached is not None:
                return cached

        if methods is None:
            methods = {}
            cls._cache[owner] = methods
        weak_method = super().__new__(cls, method)
        methods[function] = weak_method
        return weak_method


__all__ = ["WeakMethod"]

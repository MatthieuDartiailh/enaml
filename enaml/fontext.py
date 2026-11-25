# --------------------------------------------------------------------------------------
# Copyright (c) 2013-2025, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# --------------------------------------------------------------------------------------
"""
Wrapper module for Font class and related enums from Rust extension.

This module maintains backward compatibility with the C++ implementation by
re-exporting the Font class and font-related enums from the Rust extension.
"""

from enaml._rust import Font


class FontStyle:
    __module__ = "fontext"
    Normal = 0
    Italic = 1
    Oblique = 2


class FontStretch:
    __module__ = "fontext"
    UltraCondensed = 0
    ExtraCondensed = 1
    Condensed = 2
    SemiCondensed = 3
    Unstretched = 4
    SemiExpanded = 5
    Expanded = 6
    ExtraExpanded = 7
    UltraExpanded = 8


class FontCaps:
    __module__ = "fontext"
    MixedCase = 0
    AllUppercase = 1
    AllLowercase = 2
    SmallCaps = 3
    Capitalize = 4

__all__ = ['Font', 'FontStyle', 'FontStretch', 'FontCaps']

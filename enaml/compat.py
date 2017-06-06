#------------------------------------------------------------------------------
# Copyright (c) 2013-2017, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
import sys

IS_PY3 = sys.version_info >= (3,)

USE_WORDCODE = sys.version_info >= (3, 6)

if IS_PY3:
    import tokenize
    def detect_encoding(filename):
        pass
else:
    # Adapted from https://stackoverflow.com/questions/38374489/
    # get-encoding-specified-in-magic-line-shebang-from-within-module
    import re
    from codecs import lookup, BOM_UTF8

    cookie_re = re.compile(r'^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)')
    blank_re = re.compile(br'^[ \t\f]*(?:[#\r\n]|$)')

    def _get_normal_name(orig_enc):
        """Imitates get_normal_name in tokenizer.c."""
        # Only care about the first 12 characters.
        enc = orig_enc[:12].lower().replace("_", "-")
        if enc == "utf-8" or enc.startswith("utf-8-"):
            return "utf-8"
        if enc in ("latin-1", "iso-8859-1", "iso-latin-1") or \
           enc.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
            return "iso-8859-1"
        return orig_enc

    def detect_encoding(filename):
        bom_found = False
        encoding = None
        default = 'ascii'

        def find_cookie(line):
            match = cookie_re.match(line)
            if not match:
                return None
            encoding = _get_normal_name(match.group(1))
            try:
                lookup(encoding)
            except LookupError:
                # This behaviour mimics the Python interpreter
                raise SyntaxError(
                    "unknown encoding for {!r}: {}".format(
                        filename, encoding))

            if bom_found:
                if encoding != 'utf-8':
                    # This behaviour mimics the Python interpreter
                    raise SyntaxError(
                        'encoding problem for {!r}: utf-8'.format(filename))
                encoding += '-sig'
            return encoding

        with open(filename, 'rb') as fileobj:
            first = next(fileobj, '')
            if first.startswith(BOM_UTF8):
                bom_found = True
                first = first[3:]
                default = 'utf-8-sig'
            if not first:
                return default

            encoding = find_cookie(first)
            if encoding:
                return encoding
            if not blank_re.match(first):
                return default

            second = next(fileobj, '')

        if not second:
            return default
        return find_cookie(second) or default

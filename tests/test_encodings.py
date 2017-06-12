#------------------------------------------------------------------------------
# Copyright (c) 2013-2017, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
from textwrap import dedent
from utils import compile_source


def test_unicode_literal():
    source = dedent("""\
    from enaml.widgets.api import Window

    enamldef MyWindow(Window): win:
        attr test = 'I do unicode characters: αΨγ 😀⏰🏔 𠁒𠁝𠁖'
    """)
    myWindow = compile_source(source, 'MyWindow')()
    unicode_literal = 'I do unicode characters: αΨγ 😀⏰🏔 𠁒𠁝𠁖'
    assert unicode_literal == myWindow.test


def test_unicode_escape_literal():
    source = dedent("""\
    from enaml.widgets.api import Window

    enamldef MyWindow(Window): win:
        attr test = 'I do unicode characters: \\U00020052'
    """)
    myWindow = compile_source(source, 'MyWindow')()
    unicode_escape_literal = 'I do unicode characters: \U00020052'
    assert unicode_escape_literal == myWindow.test


def test_raw_unicode_literal():
    source = dedent("""\
    from enaml.widgets.api import Window

    enamldef MyWindow(Window): win:
        attr test = r'I do unicode characters: \\U00020052'
    """)
    myWindow = compile_source(source, 'MyWindow')()
    raw_unicode_literal = r'I do unicode characters: \U00020052'
    assert raw_unicode_literal == myWindow.test


def test_bytes_literal():
    source = dedent("""\
    from enaml.widgets.api import Window

    enamldef MyWindow(Window): win:
        attr test = b'I also do bytes with\\nescapes'
    """)
    myWindow = compile_source(source, 'MyWindow')()
    bytes_literal = b'I also do bytes with\nescapes'
    print(bytes_literal.decode('utf-8'))
    print(myWindow.test.decode('utf-8'))
    assert bytes_literal == myWindow.test


def test_raw_bytes_literal():
    source = dedent("""\
    from enaml.widgets.api import Window

    enamldef MyWindow(Window): win:
        attr test = rb'I do bytes with\\nescapes'
        attr test2 = br'I do bytes with\\nescapes'
    """)
    myWindow = compile_source(source, 'MyWindow')()
    raw_bytes_literal = rb'I do bytes with\nescapes'
    raw_bytes_literal2 = br'I do bytes with\nescapes'
    assert raw_bytes_literal == myWindow.test
    assert raw_bytes_literal2 == myWindow.test2


def test_unicode_identifier():
    source = dedent("""\
    from enaml.widgets.api import Window

    enamldef MyWindow(Window): win:
        attr 𠁒 = 'test'
    """)
    myWindow = compile_source(source, 'MyWindow')()
    𠁒 = 'test'
    assert 𠁒 == myWindow.𠁒


if __name__ == '__main__':
    test_unicode_literal()
    test_unicode_escape_literal()
    test_raw_unicode_literal()
    test_bytes_literal()
    test_raw_bytes_literal()
    test_unicode_identifier()

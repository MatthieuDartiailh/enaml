#------------------------------------------------------------------------------
# Copyright (c) 2013-2017, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
import os
import sys
from setuptools import find_packages, Extension, setup
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
from setuptools.command.develop import develop

sys.path.insert(0, os.path.abspath('.'))
from enaml.version import __version__
from enaml.build_tools import EnamlBuildPy, EnamlInstallLib

ext_modules = [
    Extension(
        'enaml.weakmethod',
        ['enaml/src/weakmethod.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.callableref',
        ['enaml/src/callableref.cpp'],
        language='c++',
    ),
    Extension(
       'enaml.signaling',
       ['enaml/src/signaling.cpp'],
       language='c++',
    ),
    Extension(
        'enaml.core.funchelper',
        ['enaml/src/funchelper.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.colorext',
        ['enaml/src/colorext.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.fontext',
        ['enaml/src/fontext.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.core.dynamicscope',
        ['enaml/src/dynamicscope.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.core.alias',
        ['enaml/src/alias.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.core.declarative_function',
        ['enaml/src/declarative_function.cpp'],
        language='c++',
    ),
    Extension(
        'enaml.c_compat',
        ['enaml/src/c_compat.cpp'],
        language='c++',
    )
]


if sys.platform == 'win32':
    ext_modules.append(
        Extension(
            'enaml.winutil',
            ['enaml/src/winutil.cpp'],
            libraries=['user32', 'gdi32'],
            language='c++'
        )
    )


class BuildExt(build_ext):
    """ A custom build extension for adding compiler-specific options.

    """
    c_opts = {
        'msvc': ['/EHsc']
    }

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.debug = False

    def build_extensions(self):
        ct = self.compiler.compiler_type
        opts = self.c_opts.get(ct, [])
        for ext in self.extensions:
            ext.extra_compile_args = opts
        build_ext.build_extensions(self)


class Install(install):
    """ Calls the parser to construct a lex and parse table specific
        to the system before installation.

    """

    def run(self):
        from enaml.core.parsing import write_tables
        write_tables()
        install.run(self)


class Develop(develop):
    """ Calls the parser to construct a lex and parse table specific
        to the system before installation.

    """

    def run(self):
        from enaml.core.parsing import write_tables
        write_tables()
        develop.run(self)


setup(
    name='enaml',
    version=__version__,
    author='The Nucleic Development Team',
    author_email='sccolbert@gmail.com',
    url='https://github.com/nucleic/enaml',
    description='Declarative DSL for building rich user interfaces in Python',
    long_description=open('README.rst').read(),
    requires=['atom', 'PyQt', 'ply', 'kiwisolver', 'qtpy'],
    install_requires=['setuptools', 'future', 'atom >= 0.4.0.dev',
                      'kiwisolver >= 0.2.0.dev', 'ply >= 3.4', 'qtpy'],
    packages=find_packages(),
    package_data={
        'enaml.qt.docking': [
            'dock_images/*.png',
            'dock_images/*.py',
            'enaml_dock_resources.qrc'
        ],
    },
    entry_points={'console_scripts': ['enaml-run = enaml.runner:main']},
    ext_modules=ext_modules,
    cmdclass={'build_ext': BuildExt,
              'build_py': EnamlBuildPy,
              'install': Install,
              'develop': Develop,
              'install_lib': EnamlInstallLib},
)

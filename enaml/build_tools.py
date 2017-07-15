#------------------------------------------------------------------------------
# Copyright (c) 2013-2017, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
"""Tools to make building project including enaml files easier.

To use those in you project you should:

- declare the following two functions

def enaml_build_py(*args, **kwargs):
    from enaml.build_tools import EnamlBuildPy
    return EnamlBuildPy(*args, **kwargs)

def enaml_install_lib(*args, **kwargs):
    from enaml.build_tools import EnamlInstallLib
    return EnamlInstallLib(*args, **kwargs)

- specify enaml as a setup_requires in your setup function and register the
  custom command classes as follow:

setup(name='myproject',
      setup_requires=['enaml'],
      cmdclass={'build_py': enaml_build_py,
                'install_lib': enaml_install_lib})

When building conda package you need to specify that enamlc files needs to be
ignored during binary relocation. To do so add the following to the build
section of your package:

build:
  ignore_prefix_files:
    - "**/myproject/**/__enamlcache__/*.*.enamlc"

This requires conda-build >= 3.0

"""
import os
import sys
import itertools
from glob import glob
from distutils import log

from setuptools.command.install_lib import install_lib
from setuptools.command.build_py import build_py


def enaml_byte_compile(files):
    """Byte compile enaml files in a list of files.

    """
    from .core.import_hooks import make_file_info, EnamlImporter
    for file in files:
        if not file.endswith('.enaml'):
            continue
        log.info("byte-compiling %s", file)
        file_info = make_file_info(file)
        EnamlImporter(file_info).compile_code()


class EnamlBuildPy(build_py):
    """Build command including enaml files and byte compiling them.

    To use it simply import in your setup.py and add the following line to the
    arguments of setup

        cmdclass={'build_py': BuildPyAndEnaml}

    """

    def __getattr__(self, attr):
        if attr == 'enaml_files':
            self.enaml_files = self._get_enaml_files()
            return self.enaml_files
        return build_py.__getattr__(self, attr)

    def _get_data_files(self):
        data_files = build_py._get_data_files(self)
        return data_files + self.enaml_files

    def _get_enaml_files(self):
        """Generate list of '(package,src_dir,build_dir,filenames)' tuples for
        enaml files.

        """
        self.analyze_manifest()
        return list(map(self._get_pkg_enaml_files, self.packages or ()))

    def _get_pkg_enaml_files(self, package):
        # Locate package source directory
        src_dir = self.get_package_dir(package)

        # Compute package build directory
        build_dir = os.path.join(*([self.build_lib] + package.split('.')))

        # Strip directory from globbed filenames
        filenames = [
            os.path.relpath(file, src_dir)
            for file in self.find_enaml_files(package, src_dir)
        ]
        return package, src_dir, build_dir, filenames

    def find_enaml_files(self, package, src_dir):
        """Return filenames for package's data files in 'src_dir'

        """
        patterns = self._get_platform_patterns(
            {'': ['*.enaml']},
            package,
            src_dir,
        )
        globs_expanded = map(glob, patterns)
        # flatten the expanded globs into an iterable of matches
        globs_matches = itertools.chain.from_iterable(globs_expanded)
        glob_files = filter(os.path.isfile, globs_matches)
        files = itertools.chain(
                self.manifest_files.get(package, []),
                glob_files,
            )
        return self.exclude_data_files(package, src_dir, files)

    def byte_compile(self, files):
        """Byte compile enaml files and write the cache files.

        """
        build_py.byte_compile(self, files)
        if sys.dont_write_bytecode:
            self.warn('byte-compiling is disabled, skipping.')
            return

        if self.dry_run:
            return

        if self.compile or self.optimize > 0:
            enaml_byte_compile(files)


class EnamlInstallLib(install_lib):
    """Compile enaml files when installing a lib.

    """

    def byte_compile(self, files):
        """Byte compile enaml files and write the cache files.

        """
        install_lib.byte_compile(self, files)
        if sys.dont_write_bytecode:
            self.warn('byte-compiling is disabled, skipping.')
            return

        if self.dry_run:
            return

        if self.compile or self.optimize > 0:
            enaml_byte_compile(files)

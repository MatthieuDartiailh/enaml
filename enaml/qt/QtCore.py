#------------------------------------------------------------------------------
# Copyright (c) 2013, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
from . import QT_API, PYQT4_API, PYQT5_API


if QT_API in PYQT4_API or QT_API in PYQT5_API:
    from qtpy.QtCore import *
    QDateTime.toPython = QDateTime.__dict__['toPyDateTime']
    QDate.toPython = QDate.__dict__['toPyDate']
    QTime.toPython = QTime.__dict__['toPyTime']
    __version__ = QT_VERSION_STR
    __version_info__ = tuple(map(int, QT_VERSION_STR.split('.')))
    # Remove the input hook or pdb.set_trace() will infinitely recurse
    pyqtRemoveInputHook()
else:
    from PySide import __version__, __version_info__
    from PySide.QtCore import *

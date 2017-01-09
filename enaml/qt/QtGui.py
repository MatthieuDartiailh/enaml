#------------------------------------------------------------------------------
# Copyright (c) 2013-2017, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
from . import QT_API, PYQT5_API
from qtpy.QtGui import *

ID_TRANS = QTransform() if QT_API in PYQT5_API else QMatrix()

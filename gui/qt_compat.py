"""
AirBridge - Qt Compatibility Abstraction Layer
Seamlessly supports PySide6 and PyQt6 for maximum cross-environment portability
Created by Chathunga
"""

import sys
import logging

logger = logging.getLogger("AirBridge.QtCompat")

QT_LIB = None

# Attempt PySide6 first
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    Signal = QtCore.Signal
    Slot = QtCore.Slot
    QT_LIB = "PySide6"
    logger.info("Using PySide6 Qt bindings.")
except ImportError:
    # Fallback to PyQt6
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        Signal = QtCore.pyqtSignal
        Slot = QtCore.pyqtSlot
        QT_LIB = "PyQt6"
        logger.info("Using PyQt6 Qt bindings.")
    except ImportError as e:
        logger.critical("Neither PySide6 nor PyQt6 is installed!")
        raise ImportError(
            "AirBridge requires PySide6 or PyQt6. Please install via: pip install PySide6 or pip install PyQt6"
        ) from e

__all__ = ["QtCore", "QtGui", "QtWidgets", "Signal", "Slot", "QT_LIB"]

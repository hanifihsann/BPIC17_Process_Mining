"""Entry point for the BPIC17 desktop application."""

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.pages import install_anggota4_pages
from gui.styles import STYLESHEET


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("BPIC17 Process Mining")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    install_anggota4_pages(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

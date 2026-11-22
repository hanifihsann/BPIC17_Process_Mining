"""Entry point for the BPIC17 desktop application."""

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.pages import install_anggota4_pages
from gui.styles import STYLESHEET


def setup_feature_pages(window: MainWindow) -> None:
    """Mount completed feature pages onto MainWindow."""
    from gui.pages.exercise_117_page import Exercise117Page
    from gui.pages.export_page import ExportPage
    from gui.pages.exercise_115_118_page import Exercise115118Page

    # Hasta: Exercises 11.15 and 11.18
    ex115118_page = Exercise115118Page()
    window.install_page(
        "exercise_115_118",
        ex115118_page,
        ex115118_page.bind_main_window(window),
    )

    # Member 2: Exercise 11.7
    ex117_page = Exercise117Page(state=window.state)
    window.install_page("exercise_117", ex117_page)
    window.state.dataset_changed.connect(
        lambda ds: ex117_page.set_dataset(
            ds.log if ds else None, ds.metadata if ds else None, ds.overview if ds else None
        )
    )
    ex117_page.analysis_completed.connect(
        lambda res: window.state.save_result(window.state.dataset, "exercise_117", res)
        if window.state.dataset else None
    )

    # Member 2: Export Results
    export_page = ExportPage(window.state, ex117_page=ex117_page)
    window.install_page("export", export_page)

    # Member 4: Case Explorer & Exercise 11.22
    try:
        _, ce_page = install_anggota4_pages(window)

        def open_in_ce(case_id, evidence):
            ce_page.open_case(case_id, evidence)
            window.navigate("case_explorer")

        ex117_page.open_case_requested.connect(open_in_ce)
        ex115118_page.open_case_requested.connect(open_in_ce)
    except Exception as exc:
        logging.getLogger(__name__).warning("Modul halaman tambahan belum siap: %s", exc)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("BPIC17 Process Mining")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    setup_feature_pages(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

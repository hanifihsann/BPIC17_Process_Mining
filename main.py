"""Entry point for the BPIC17 desktop application."""

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.styles import STYLESHEET


def setup_feature_pages(window: MainWindow) -> None:
    """Mount completed feature pages onto MainWindow."""
    from gui.pages.exercise_117_page import Exercise117Page
    from gui.pages.export_page import ExportPage
    from modules.exercise_117 import analyze_117

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
        from gui.pages.case_explorer_page import CaseExplorerPage
        from gui.pages.exercise_1122_page import Exercise1122Page

        ce_page = CaseExplorerPage()
        window.install_page("case_explorer", ce_page)
        window.state.dataset_changed.connect(
            lambda ds: ce_page.set_dataset(
                ds.log if ds else None, ds.metadata if ds else None, ds.overview if ds else None
            )
        )

        ex1122_page = Exercise1122Page()
        window.install_page("exercise_1122", ex1122_page)
        window.state.dataset_changed.connect(
            lambda ds: ex1122_page.set_dataset(
                ds.log if ds else None, ds.metadata if ds else None, ds.overview if ds else None
            )
        )

        # Cross-page navigation
        def open_in_ce(case_id, evidence):
            ce_page.open_case(case_id, evidence)
            window.navigate("case_explorer")

        ex117_page.open_case_requested.connect(open_in_ce)
        ex1122_page.open_case_requested.connect(open_in_ce)
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

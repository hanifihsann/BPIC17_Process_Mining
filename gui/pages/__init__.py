"""Reusable PySide6 page widgets and MainWindow installer owned by Member 4."""

from __future__ import annotations

from typing import Any

from gui.pages.case_explorer_page import CaseExplorerPage
from gui.pages.exercise_1122_page import Exercise1122Page


def install_anggota4_pages(window: Any) -> tuple[Exercise1122Page, CaseExplorerPage]:
    """Install Exercise 11.22 and Case Explorer into Member 5's ``MainWindow``.

    Wires ``TaskControls``, ``AppState`` (``dataset_changed`` / ``result_changed``),
    and cross-page evidence navigation from Exercise 11.22 to Case Explorer.
    """

    ex1122_page = Exercise1122Page()
    case_explorer_page = CaseExplorerPage()

    controls = ex1122_page.bind_main_window(window)
    case_explorer_page.bind_main_window(window)

    window.install_page("exercise_1122", ex1122_page, controls)
    window.install_page("case_explorer", case_explorer_page)

    def _open_evidence(case_id: Any, evidence: Any) -> None:
        case_explorer_page.open_case(case_id, evidence)
        window.navigate("case_explorer")

    ex1122_page.open_case_requested.connect(_open_evidence)
    return ex1122_page, case_explorer_page


__all__ = ["Exercise1122Page", "CaseExplorerPage", "install_anggota4_pages"]

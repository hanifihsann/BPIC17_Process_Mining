"""Verify the complete desktop workflow on a local BPIC17 XES file."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from time import monotonic
from unittest.mock import patch

os.environ.setdefault("TQDM_DISABLE", "1")

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QFileDialog

from gui.main_window import MainWindow
from gui.styles import STYLESHEET
from main import setup_feature_pages


KEYS = ("exercise_117", "exercise_115_118", "exercise_1122")


def wait_until(condition, label: str, timeout_ms: int = 180_000) -> None:
    if condition():
        return
    loop = QEventLoop()
    poll = QTimer(loop)
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    poll.start(20)
    QTimer.singleShot(timeout_ms, loop, loop.quit)
    loop.exec()
    poll.stop()
    if not condition():
        raise TimeoutError(label)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify(xes: Path, output: Path | None, csv_dir: Path) -> dict:
    app = QApplication([])
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    setup_feature_pages(window)
    window.resize(1240, 760)
    window.show()

    def screenshot(name: str) -> None:
        app.processEvents()
        if output is not None and not window.grab().save(str(output / f"{name}.png")):
            raise OSError(f"Gagal menyimpan screenshot {name}")

    timings = {}
    try:
        screenshot("01_import")
        started = monotonic()
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(xes), "XES")):
            window.import_page.select_button.click()
        assert window.busy
        wait_until(lambda: not window.busy, "Impor BPIC17")
        timings["import_seconds"] = round(monotonic() - started, 2)
        dataset = window.state.dataset
        assert dataset is not None, window.feedback.message_label.toolTip()
        assert dataset.metadata["case_count"] == dataset.overview["case_count"] == 31_509
        assert dataset.metadata["event_count"] == dataset.overview["event_count"] == 1_202_267
        assert window.import_page.case_table.model().rowCount() == 31_509
        window.navigate("overview")
        screenshot("02_overview")

        pages = {key: window._page_widgets[key] for key in (*KEYS, "case_explorer", "export")}
        explorer = pages["case_explorer"]
        wait_until(lambda: not explorer.is_indexing(), "Indeks Case Explorer")

        captures = {
            "exercise_117": "03_exercise_117",
            "exercise_115_118": "04_exercise_115",
            "exercise_1122": "06_exercise_1122",
        }

        def run(key: str) -> dict:
            page = pages[key]
            window.navigate(key)
            started = monotonic()
            button = page.run_button if key == "exercise_117" else page.task_controls.run_button
            assert button.isEnabled(), key
            button.click()
            assert window.busy, key
            wait_until(lambda: not window.busy, key)
            timings.setdefault(key, round(monotonic() - started, 2))
            result = window.state.result(key)
            assert result is not None, window.feedback.message_label.toolTip()
            return result

        results = {}
        for key in KEYS:
            results[key] = run(key)
            screenshot(captures[key])
            if key == "exercise_115_118":
                pages[key].tabs.setCurrentIndex(1)
                screenshot("05_exercise_118")

        loan = results["exercise_117"]
        fraud = results["exercise_115_118"]
        cancelled = results["exercise_1122"]
        counts = [loan["11.7_a"]["count"], *(loan[f"11.7_{x}"]["count"] for x in "cde"),
                  fraud["11.15"]["count"], fraud["11.18"]["count"], cancelled["count"]]
        assert counts == [31_509, 17_228, 3_720, 4_436, 13, 3, 902], counts
        assert all(result["total_cases"] == 31_509 for result in results.values())
        assert abs(cancelled["percentage"] - 902 / 31_509 * 100) < 1e-9
        mean_days = {code: loan[f"11.7_{code.lower()}"]["mean_cycle_time_days"] for code in "BCDE"}
        for code, expected in zip("BCDE", (21.899606, 18.134257, 16.877526, 23.510446)):
            assert math.isclose(mean_days[code], expected, abs_tol=1e-6), mean_days

        evidence_output = {}
        for code, key, evidence in (
            ("117c", "exercise_117", loan["11.7_c"]["evidence"][0]),
            ("115", "exercise_115_118", fraud["11.15"]["evidence"][0]),
            ("118", "exercise_115_118", fraud["11.18"]["evidence"][0]),
            ("1122", "exercise_1122", cancelled["evidence"][0]),
        ):
            page = pages[key]
            window.navigate(key)
            if code == "117c":
                page.category_combo.setCurrentIndex(1)
                page.result_table.selectRow(0)
                page.open_explorer_button.click()
            elif code in ("115", "118"):
                exercise = "11.15" if code == "115" else "11.18"
                page.tabs.setCurrentIndex(0 if code == "115" else 1)
                page._table_widgets[exercise].selectRow(0)
                page._open_buttons[exercise].click()
            else:
                page.result_table.cellDoubleClicked.emit(0, 0)
            assert window.stack.currentWidget() is explorer, code
            assert explorer._current_case_id == evidence["case_id"], code
            highlighted = {
                row for row in range(explorer.event_table.rowCount())
                if explorer.event_table.item(row, 5).text().startswith("Evidence")
            }
            assert highlighted == set(evidence["evidence_positions"]), code
            evidence_output[code] = {
                "case_id": evidence["case_id"],
                "trace_events": explorer.event_table.rowCount(),
                "positions_1_based": sorted(row + 1 for row in highlighted),
                "resource": evidence.get("resource_id"),
                "activity": [explorer.event_table.item(row, 2).text() for row in sorted(highlighted)],
                "lifecycle": [explorer.event_table.item(row, 3).text() for row in sorted(highlighted)],
            }
            positions = sorted(highlighted)
            for name, position in ((f"evidence_{code}", positions[0]),
                                   (f"evidence_{code}_lanjutan", positions[-1])):
                if name.endswith("_lanjutan") and len(positions) == 1:
                    continue
                app.processEvents()
                item = explorer.event_table.item(position, 0)
                explorer.event_table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                screenshot(name)
                assert explorer.event_table.viewport().rect().intersects(
                    explorer.event_table.visualItemRect(item)
                ), name
        screenshot("07_case_explorer")

        export = pages["export"]
        window.navigate("export")
        screenshot("08_export")

        def export_file(button, target: Path) -> list[dict[str, str]]:
            assert button.isEnabled(), target
            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "CSV")):
                button.click()
            assert window.busy, target
            wait_until(lambda: not window.busy, "Ekspor CSV")
            assert target.is_file(), export.status_label.text()
            return read_csv(target)

        summary = export_file(export.btn_export_summary, csv_dir / "summary.csv")
        codes = [row["Kode"] for row in summary]
        assert codes == ["11.7 A", "11.7 B", "11.7 C", "11.7 D", "11.7 E", "11.15", "11.18", "11.22"]
        assert all(row["Aturan / Filter"] and row["Total Case Aktif (Denominator)"] == "31509" for row in summary)
        exported = {}
        for index, code, expected in ((0, "117", sum(counts[1:4])), (4, "115", 13), (5, "118", 3), (6, "1122", 902)):
            export.category_combo.setCurrentIndex(index)
            rows = export_file(export.btn_export_cases, csv_dir / f"cases_{code}.csv")
            assert len(rows) == expected, (code, len(rows))
            assert all(row["Case ID"] and row["Posisi Evidence (0-based)"] for row in rows), code
            exported[code] = len(rows)

        for key in KEYS:
            page = pages[key]
            window.navigate(key)
            if key == "exercise_117":
                page.reset_button.click()
                assert page.summary_table.rowCount() == 0
                new_result = run(key)
                fields = ("11.7_a", "11.7_b", "11.7_c", "11.7_d", "11.7_e")
                assert all(new_result[code] == results[key][code] for code in fields)
            else:
                page.task_controls.reset_button.click()
                assert window.state.result(key) is None
                page.task_controls.rerun_button.click()
                assert window.busy
                wait_until(lambda: not window.busy, f"Jalankan ulang {key}")
                assert window.state.result(key) == results[key], key

        window.navigate("about")
        screenshot("09_about")
        return {"counts": counts, "mean_days": mean_days, "percentage_1122": cancelled["percentage"],
                "evidence": evidence_output, "csv_rows": exported, "seconds": timings}
    finally:
        if window.busy:
            wait_until(lambda: not window.busy, "Pembersihan GUI")
        window.close()
        app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xes", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bpic17-verify-") as tmp:
        result = verify(args.xes.resolve(), args.screenshots, Path(tmp))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

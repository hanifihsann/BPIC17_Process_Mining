"""CSV Export utilities for BPIC17 Process Mining analysis results.

Provides clean, structured CSV export functionality for:
1. Analysis summary metrics (exercise codes, rules, counts, denominators, percentages, mean cycle times).
2. Filtered case lists and evidence records (Case ID, category, duration, timestamps, evidence positions).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


SUMMARY_HEADERS = [
    "Kode",
    "Subsoal",
    "Pertanyaan",
    "Aturan / Filter",
    "Jumlah Case Terpilih",
    "Total Case Aktif (Denominator)",
    "Persentase (%)",
    "Rata-rata Cycle Time (Hari)",
]

def _summary_rows(results: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []

    # If it is an Exercise 11.7 result dict
    if results.get("exercise") == "11.7":
        total_cases = results.get("total_cases", 0)

        # 11.7 A
        sub_a = results.get("11.7_a", {})
        rows.append([
            "11.7 A",
            sub_a.get("subsoal", "11.7 A"),
            sub_a.get("question", "Jumlah keseluruhan case"),
            sub_a.get("rule", ""),
            sub_a.get("count", total_cases),
            total_cases,
            100.0 if total_cases > 0 else 0.0,
            "-",
        ])

        # 11.7 B
        sub_b = results.get("11.7_b", {})
        mean_b = sub_b.get("mean_cycle_time_days", 0.0)
        valid_count = sub_b.get("valid_duration_cases", total_cases)
        rows.append([
            "11.7 B",
            sub_b.get("subsoal", "11.7 B"),
            sub_b.get("question", "Rata-rata cycle time seluruh case"),
            sub_b.get("rule", ""),
            valid_count,
            total_cases,
            100.0 * valid_count / total_cases if total_cases else 0.0,
            f"{mean_b:.4f}" if isinstance(mean_b, (int, float)) else str(mean_b),
        ])

        # 11.7 C, D, E
        for key in ("11.7_c", "11.7_d", "11.7_e"):
            sub = results.get(key, {})
            if sub:
                mean_val = sub.get("mean_cycle_time_days", 0.0)
                mean_str = f"{mean_val:.4f}" if isinstance(mean_val, (int, float)) else str(mean_val)
                pct_val = sub.get("percentage", 0.0)
                pct_str = f"{pct_val:.2f}%" if isinstance(pct_val, (int, float)) else str(pct_val)
                rows.append([
                    sub.get("subsoal", key.upper()),
                    sub.get("subsoal", key.upper()),
                    sub.get("question", ""),
                    sub.get("rule", ""),
                    sub.get("count", 0),
                    sub.get("total_cases", total_cases),
                    pct_str,
                    mean_str,
                ])
    elif results.get("exercise") in {"11.15 & 11.18", "11.22"}:
        total = results["total_cases"]
        codes = ("11.15", "11.18") if results["exercise"] == "11.15 & 11.18" else ("11.22",)
        questions = {
            "11.15": "Case dengan minimal dua penyelesaian aktivitas fraud",
            "11.18": "Case dengan minimal dua penyelesaian oleh resource yang sama",
            "11.22": "Case dengan O_Cancelled sebelum O_Accepted",
        }
        for code in codes:
            section = results if code == "11.22" else results[code]
            count = section["count"]
            percentage = 100 * count / total if total else 0.0
            rows.append([code, code, questions[code], section["rule"], count, total, percentage, "-"])
    else:
        rows.extend(list(row) for row in results.get("rows", []))
    return rows


def _write_csv(filepath: str | Path, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> Path:
    """Replace the destination only after all CSV rows have been written."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with NamedTemporaryFile(
            dir=path.parent, mode="w", newline="", encoding="utf-8-sig", delete=False
        ) as file:
            temp_path = Path(file.name)
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(rows)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return path


def export_summary_to_csv(results: dict[str, Any], filepath: str | Path) -> Path:
    """Export the summary of one analysis."""
    return _write_csv(filepath, SUMMARY_HEADERS, _summary_rows(results))


def export_completed_summary_to_csv(
    results: Iterable[dict[str, Any]], filepath: str | Path
) -> Path:
    """Export completed analyses into a single summary CSV."""
    return _write_csv(filepath, SUMMARY_HEADERS, (row for result in results for row in _summary_rows(result)))


def export_cases_to_csv(
    cases_or_evidence: Sequence[dict[str, Any]],
    filepath: str | Path,
    *,
    category_title: str = "Exercise 11.7 Filtered Cases",
) -> Path:
    """Export filtered cases and their evidence records to a CSV file.

    Parameters:
        cases_or_evidence: List of case dicts or evidence records.
        filepath: Destination file path.
        category_title: Optional title/category description.

    Returns:
        Path object pointing to the written CSV file.
    """
    headers = [
        "Case ID",
        "Kategori / Subsoal",
        "Aktivitas Target",
        "Jumlah Kemunculan Target",
        "Posisi Evidence (0-based)",
        "Durasi Case (Hari)",
        "Jumlah Event Trace",
        "Timestamp Event Pertama",
        "Timestamp Event Terakhir",
        "Resource",
        "Timestamp Evidence",
        "Lifecycle Evidence",
        "Aturan / Filter",
        "Total Case Aktif (Denominator)",
    ]

    rows: list[list[Any]] = []

    for item in cases_or_evidence:
        case_id = item.get("case_id", "")
        subsoal = item.get("subsoal", category_title)
        activity = item.get("activity", item.get("label", "-"))
        occ_count = item.get("occurrence_count", len(item.get("evidence_positions", [])))
        positions = ";".join(str(p) for p in item.get("evidence_positions", []))
        dur = item.get("duration_days")
        dur_str = f"{dur:.4f}" if isinstance(dur, (int, float)) else ("-" if dur is None else str(dur))
        trace_len = item.get("trace_length", "-")
        first_ts = item.get("first_timestamp", "")
        last_ts = item.get("last_timestamp", "")
        evidence_events = item.get("evidence_events", [])
        if "cancelled_event" in item:
            evidence_events = (item["cancelled_event"], item["accepted_event"])
            activity = " → ".join(event["activity"] for event in evidence_events)
        evidence_timestamps = ";".join(str(event["timestamp"]) for event in evidence_events)
        evidence_lifecycle = ";".join(str(event.get("lifecycle") or "-") for event in evidence_events)

        rows.append([
            case_id,
            subsoal,
            activity,
            occ_count,
            positions,
            dur_str,
            trace_len,
            str(first_ts) if first_ts is not None else "",
            str(last_ts) if last_ts is not None else "",
            item.get("resource_id"),
            evidence_timestamps,
            evidence_lifecycle,
            item.get("rule"),
            item.get("total_cases"),
        ])

    return _write_csv(filepath, headers, rows)


def case_export_rows(
    result: dict[str, Any], codes: Sequence[str]
) -> list[dict[str, Any]]:
    """Attach the exercise rule and denominator to each existing evidence row."""
    rows = []
    for code in codes:
        if code.startswith("11.7 "):
            section = result["11.7_" + code[-1].lower()]
        else:
            section = result if code == "11.22" else result[code]
        rows.extend(
            {
                **item,
                "subsoal": code,
                "rule": section["rule"],
                "total_cases": result["total_cases"],
            }
            for item in section["evidence"]
        )
    return rows

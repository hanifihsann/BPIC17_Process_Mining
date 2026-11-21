"""CSV Export utilities for BPIC17 Process Mining analysis results.

Provides clean, structured CSV export functionality for:
1. Analysis summary metrics (exercise codes, rules, counts, denominators, percentages, mean cycle times).
2. Filtered case lists and evidence records (Case ID, category, duration, timestamps, evidence positions).
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def export_summary_to_csv(
    results: dict[str, Any],
    filepath: str | Path,
) -> Path:
    """Export exercise analysis summary metrics to a CSV file.

    Parameters:
        results: Result dict, such as that returned by ``analyze_117`` or multi-exercise dictionaries.
        filepath: Destination file path.

    Returns:
        Path object pointing to the written CSV file.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "Kode",
        "Subsoal",
        "Pertanyaan",
        "Aturan / Filter",
        "Jumlah Case Terpilih",
        "Total Case Aktif (Denominator)",
        "Persentase (%)",
        "Rata-rata Cycle Time (Hari)",
    ]

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
        rows.append([
            "11.7 B",
            sub_b.get("subsoal", "11.7 B"),
            sub_b.get("question", "Rata-rata cycle time seluruh case"),
            sub_b.get("rule", ""),
            sub_b.get("valid_duration_cases", total_cases),
            total_cases,
            100.0 if total_cases > 0 else 0.0,
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
    else:
        # Generic table export if results are provided as custom rows
        for row in results.get("rows", []):
            rows.append(list(row))

    with open(path, mode="w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    return path


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
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

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
        ])

    with open(path, mode="w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    return path

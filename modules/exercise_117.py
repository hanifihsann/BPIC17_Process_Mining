"""Exercise 11.7 analysis: Overall, Successful, Unsuccessful, and Canceled Cases.

This module operates strictly on an already-loaded PM4Py ``EventLog`` or PM4Py
``pandas.DataFrame`` without reading XES files again or mutating the input.
All calculations are performed dynamically on the active dataset.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from pm4py.objects.log.obj import EventLog


DEFAULT_ACCEPTED_ACTIVITY = "O_Accepted"
DEFAULT_REFUSED_ACTIVITY = "O_Refused"
DEFAULT_CANCELLED_ACTIVITY = "O_Cancelled"

RULE_117_A = "Hitung unique case/trace dari keseluruhan log aktif"
RULE_117_B = "Durasi tiap case = waktu event terakhir − event pertama pada trace asli"
RULE_117_C = "Case memuat setidaknya satu event O_Accepted (contains rule)"
RULE_117_D = "Case memuat setidaknya satu event O_Refused (contains rule)"
RULE_117_E = "Event TERAKHIR pada trace adalah O_Cancelled (endpoint rule)"

REQUIRED_DF_COLUMNS = ("case:concept:name", "concept:name", "time:timestamp")


def _is_missing(value: Any) -> bool:
    """Return True when a scalar value is None, NaN, or pd.NA."""
    if value is None:
        return True
    try:
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False
    except Exception:
        return False


def _clean_optional(value: Any) -> Any:
    """Return None when an optional attribute is missing, else the original value."""
    return None if _is_missing(value) else value


def _parse_timestamp(value: Any) -> pd.Timestamp | None:
    """Parse one timestamp without modifying the source value."""
    if _is_missing(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value)
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return pd.Timestamp(parsed)
    except (TypeError, ValueError, OverflowError):
        return None


def _build_event_snapshot(
    position: int,
    activity: Any,
    timestamp: Any,
    lifecycle: Any,
    resource: Any,
) -> dict[str, Any]:
    """Build a serializable snapshot of one event in trace order."""
    return {
        "position": position,
        "seq": position + 1,
        "activity": activity,
        "timestamp": timestamp,
        "lifecycle": _clean_optional(lifecycle),
        "resource": _clean_optional(resource),
    }


def _extract_cases_from_event_log(log: EventLog) -> list[tuple[Any, list[dict[str, Any]]]]:
    """Validate and extract ordered case event sequences from a PM4Py EventLog."""
    cases: list[tuple[Any, list[dict[str, Any]]]] = []
    for trace_idx, trace in enumerate(log):
        case_id = trace.attributes.get("concept:name")
        if _is_missing(case_id):
            raise ValueError(
                f"Trace indeks {trace_idx} tidak memiliki atribut wajib 'concept:name' (Case ID)."
            )

        case_events: list[dict[str, Any]] = []
        for event_idx, event in enumerate(trace):
            activity = event.get("concept:name")
            if _is_missing(activity):
                raise ValueError(
                    f"Event {event_idx} pada Case '{case_id}' tidak memiliki atribut 'concept:name'."
                )
            case_events.append(
                _build_event_snapshot(
                    position=event_idx,
                    activity=activity,
                    timestamp=event.get("time:timestamp"),
                    lifecycle=event.get("lifecycle:transition"),
                    resource=event.get("org:resource"),
                )
            )
        cases.append((case_id, case_events))
    return cases


def _extract_cases_from_dataframe(df: pd.DataFrame) -> list[tuple[Any, list[dict[str, Any]]]]:
    """Validate and extract ordered case event sequences from a PM4Py DataFrame."""
    missing_cols = [col for col in REQUIRED_DF_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"DataFrame tidak memiliki kolom wajib PM4Py: {', '.join(missing_cols)}."
        )

    if df.empty:
        return []

    if df["case:concept:name"].isna().any():
        raise ValueError("Ditemukan baris tanpa nilai 'case:concept:name' (Case ID).")
    if df["concept:name"].isna().any():
        raise ValueError("Ditemukan baris tanpa nilai 'concept:name' (Activity).")

    has_lifecycle = "lifecycle:transition" in df.columns
    has_resource = "org:resource" in df.columns

    cases: list[tuple[Any, list[dict[str, Any]]]] = []
    # sort=False preserves the existing event log order
    grouped = df.groupby("case:concept:name", sort=False)

    for case_id, group in grouped:
        case_events: list[dict[str, Any]] = []
        for pos, (_, row) in enumerate(group.iterrows()):
            case_events.append(
                _build_event_snapshot(
                    position=pos,
                    activity=row["concept:name"],
                    timestamp=row["time:timestamp"],
                    lifecycle=row["lifecycle:transition"] if has_lifecycle else None,
                    resource=row["org:resource"] if has_resource else None,
                )
            )
        cases.append((case_id, case_events))
    return cases


def _calculate_case_duration(events: list[dict[str, Any]]) -> tuple[pd.Timestamp | None, pd.Timestamp | None, float | None]:
    """Calculate the duration of a case from its first and last event timestamps.

    Returns:
        (first_timestamp, last_timestamp, duration_days)
    """
    if not events:
        return None, None, None

    first_ts = _parse_timestamp(events[0]["timestamp"])
    last_ts = _parse_timestamp(events[-1]["timestamp"])

    if first_ts is None or last_ts is None:
        return first_ts, last_ts, None

    diff = last_ts - first_ts
    if not isinstance(diff, timedelta):
        diff = timedelta(seconds=diff.total_seconds())

    duration_days = diff.total_seconds() / 86400.0
    return first_ts, last_ts, duration_days


def analyze_117(
    log_or_df: Any,
    *,
    accepted_activity: str = DEFAULT_ACCEPTED_ACTIVITY,
    refused_activity: str = DEFAULT_REFUSED_ACTIVITY,
    cancelled_activity: str = DEFAULT_CANCELLED_ACTIVITY,
) -> dict[str, Any]:
    """Execute dynamic analysis for Exercise 11.7 (A–E).

    Parameters:
        log_or_df: PM4Py ``EventLog`` or ``pandas.DataFrame``
        accepted_activity: Activity name representing an accepted offer (default 'O_Accepted')
        refused_activity: Activity name representing a refused offer (default 'O_Refused')
        cancelled_activity: Activity name representing a canceled offer (default 'O_Cancelled')

    Returns:
        Structured dictionary containing results for 11.7 A through 11.7 E,
        including counts, mean cycle time in days, matching case IDs, and evidence records.
    """
    if log_or_df is None:
        raise ValueError("Dataset tidak boleh None.")

    if isinstance(log_or_df, EventLog):
        cases = _extract_cases_from_event_log(log_or_df)
    elif isinstance(log_or_df, pd.DataFrame):
        cases = _extract_cases_from_dataframe(log_or_df)
    else:
        raise TypeError(
            f"Tipe dataset '{type(log_or_df).__name__}' tidak didukung. "
            "Gunakan pm4py.objects.log.obj.EventLog atau pandas.DataFrame."
        )

    total_cases = len(cases)

    # Empty dataset handling
    if total_cases == 0:
        return {
            "exercise": "11.7",
            "total_cases": 0,
            "11.7_a": {
                "subsoal": "11.7 A",
                "question": "Berapa jumlah keseluruhan case?",
                "rule": RULE_117_A,
                "count": 0,
            },
            "11.7_b": {
                "subsoal": "11.7 B",
                "question": "Berapa rata-rata cycle time seluruh case?",
                "rule": RULE_117_B,
                "count": 0,
                "valid_duration_cases": 0,
                "mean_cycle_time_days": 0.0,
            },
            "11.7_c": {
                "subsoal": "11.7 C",
                "question": "Berapa successful cases dan rata-rata cycle time-nya?",
                "rule": RULE_117_C,
                "target_activity": accepted_activity,
                "count": 0,
                "total_cases": 0,
                "percentage": 0.0,
                "mean_cycle_time_days": 0.0,
                "case_ids": [],
                "evidence": [],
            },
            "11.7_d": {
                "subsoal": "11.7 D",
                "question": "Berapa unsuccessful cases dan rata-rata cycle time-nya?",
                "rule": RULE_117_D,
                "target_activity": refused_activity,
                "count": 0,
                "total_cases": 0,
                "percentage": 0.0,
                "mean_cycle_time_days": 0.0,
                "case_ids": [],
                "evidence": [],
            },
            "11.7_e": {
                "subsoal": "11.7 E",
                "question": "Berapa canceled cases dan rata-rata cycle time-nya?",
                "rule": RULE_117_E,
                "target_activity": cancelled_activity,
                "count": 0,
                "total_cases": 0,
                "percentage": 0.0,
                "mean_cycle_time_days": 0.0,
                "case_ids": [],
                "evidence": [],
            },
            "cases_summary": [],
        }

    # Tracking per-case evaluations
    all_durations: list[float] = []

    c_case_ids: list[Any] = []
    c_durations: list[float] = []
    c_evidence: list[dict[str, Any]] = []

    d_case_ids: list[Any] = []
    d_durations: list[float] = []
    d_evidence: list[dict[str, Any]] = []

    e_case_ids: list[Any] = []
    e_durations: list[float] = []
    e_evidence: list[dict[str, Any]] = []

    cases_summary: list[dict[str, Any]] = []

    for case_id, events in cases:
        first_ts, last_ts, dur_days = _calculate_case_duration(events)
        if dur_days is not None:
            all_durations.append(dur_days)

        trace_length = len(events)
        has_accepted = False
        has_refused = False
        ends_with_cancelled = False

        accepted_positions: list[int] = []
        accepted_events: list[dict[str, Any]] = []
        refused_positions: list[int] = []
        refused_events: list[dict[str, Any]] = []

        for idx, ev in enumerate(events):
            act = ev["activity"]
            if act == accepted_activity:
                has_accepted = True
                accepted_positions.append(idx)
                accepted_events.append(ev)
            if act == refused_activity:
                has_refused = True
                refused_positions.append(idx)
                refused_events.append(ev)

        # 11.7 E endpoint check: ONLY the last event in trace
        if trace_length > 0 and events[-1]["activity"] == cancelled_activity:
            ends_with_cancelled = True

        # 11.7 C: contains O_Accepted
        if has_accepted:
            c_case_ids.append(case_id)
            if dur_days is not None:
                c_durations.append(dur_days)
            c_evidence.append({
                "case_id": case_id,
                "subsoal": "11.7 C",
                "activity": accepted_activity,
                "evidence_positions": accepted_positions,
                "label": accepted_activity,
                "occurrence_count": len(accepted_positions),
                "duration_days": dur_days,
                "trace_length": trace_length,
                "first_timestamp": first_ts,
                "last_timestamp": last_ts,
                "evidence_events": accepted_events,
            })

        # 11.7 D: contains O_Refused
        if has_refused:
            d_case_ids.append(case_id)
            if dur_days is not None:
                d_durations.append(dur_days)
            d_evidence.append({
                "case_id": case_id,
                "subsoal": "11.7 D",
                "activity": refused_activity,
                "evidence_positions": refused_positions,
                "label": refused_activity,
                "occurrence_count": len(refused_positions),
                "duration_days": dur_days,
                "trace_length": trace_length,
                "first_timestamp": first_ts,
                "last_timestamp": last_ts,
                "evidence_events": refused_events,
            })

        # 11.7 E: ends with O_Cancelled
        if ends_with_cancelled:
            last_event_idx = trace_length - 1
            e_case_ids.append(case_id)
            if dur_days is not None:
                e_durations.append(dur_days)
            e_evidence.append({
                "case_id": case_id,
                "subsoal": "11.7 E",
                "activity": cancelled_activity,
                "evidence_positions": [last_event_idx],
                "label": cancelled_activity,
                "occurrence_count": 1,
                "duration_days": dur_days,
                "trace_length": trace_length,
                "first_timestamp": first_ts,
                "last_timestamp": last_ts,
                "evidence_events": [events[-1]],
            })

        cases_summary.append({
            "case_id": case_id,
            "trace_length": trace_length,
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
            "duration_days": dur_days,
            "has_accepted": has_accepted,
            "has_refused": has_refused,
            "ends_with_cancelled": ends_with_cancelled,
        })

    # Calculations
    mean_all = sum(all_durations) / len(all_durations) if all_durations else 0.0
    mean_c = sum(c_durations) / len(c_durations) if c_durations else 0.0
    mean_d = sum(d_durations) / len(d_durations) if d_durations else 0.0
    mean_e = sum(e_durations) / len(e_durations) if e_durations else 0.0

    pct_c = (len(c_case_ids) / total_cases * 100.0) if total_cases > 0 else 0.0
    pct_d = (len(d_case_ids) / total_cases * 100.0) if total_cases > 0 else 0.0
    pct_e = (len(e_case_ids) / total_cases * 100.0) if total_cases > 0 else 0.0

    return {
        "exercise": "11.7",
        "total_cases": total_cases,
        "11.7_a": {
            "subsoal": "11.7 A",
            "question": "Berapa jumlah keseluruhan case?",
            "rule": RULE_117_A,
            "count": total_cases,
        },
        "11.7_b": {
            "subsoal": "11.7 B",
            "question": "Berapa rata-rata cycle time seluruh case?",
            "rule": RULE_117_B,
            "count": total_cases,
            "valid_duration_cases": len(all_durations),
            "mean_cycle_time_days": mean_all,
        },
        "11.7_c": {
            "subsoal": "11.7 C",
            "question": "Berapa successful cases dan rata-rata cycle time-nya?",
            "rule": RULE_117_C,
            "target_activity": accepted_activity,
            "count": len(c_case_ids),
            "total_cases": total_cases,
            "percentage": pct_c,
            "mean_cycle_time_days": mean_c,
            "case_ids": c_case_ids,
            "evidence": c_evidence,
        },
        "11.7_d": {
            "subsoal": "11.7 D",
            "question": "Berapa unsuccessful cases dan rata-rata cycle time-nya?",
            "rule": RULE_117_D,
            "target_activity": refused_activity,
            "count": len(d_case_ids),
            "total_cases": total_cases,
            "percentage": pct_d,
            "mean_cycle_time_days": mean_d,
            "case_ids": d_case_ids,
            "evidence": d_evidence,
        },
        "11.7_e": {
            "subsoal": "11.7 E",
            "question": "Berapa canceled cases dan rata-rata cycle time-nya?",
            "rule": RULE_117_E,
            "target_activity": cancelled_activity,
            "count": len(e_case_ids),
            "total_cases": total_cases,
            "percentage": pct_e,
            "mean_cycle_time_days": mean_e,
            "case_ids": e_case_ids,
            "evidence": e_evidence,
        },
        "cases_summary": cases_summary,
    }

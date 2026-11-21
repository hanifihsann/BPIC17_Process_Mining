"""Exercise 11.22 analysis: O_Cancelled followed by O_Accepted at case level.

This module operates strictly on an already-loaded PM4Py ``EventLog`` or PM4Py
``pandas.DataFrame`` without reading XES files again or mutating the input.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pm4py.objects.log.obj import EventLog

DEFAULT_CANCELLED_ACTIVITY = "O_Cancelled"
DEFAULT_ACCEPTED_ACTIVITY = "O_Accepted"
RULE_DESCRIPTION = (
    "O_Cancelled pada posisi i diikuti O_Accepted pada posisi j dengan i < j "
    "(analisis level case, urutan event asli dipertahankan)"
)

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


def _evaluate_case_events(
    case_id: Any,
    events: list[dict[str, Any]],
    cancelled_activity: str,
    accepted_activity: str,
) -> dict[str, Any] | None:
    """Evaluate one case's ordered events for Exercise 11.22.

    Finds the earliest ``cancelled_activity`` at index ``i`` followed by the
    earliest ``accepted_activity`` at index ``j`` with ``i < j``. Multiple
    valid pairs in the same case produce a single case-level evidence record.
    """

    first_cancelled: dict[str, Any] | None = None
    first_accepted: dict[str, Any] | None = None

    for event in events:
        activity = event["activity"]
        if first_cancelled is None:
            if activity == cancelled_activity:
                first_cancelled = event
        elif activity == accepted_activity:
            first_accepted = event
            break

    if first_cancelled is None or first_accepted is None:
        return None

    return {
        "case_id": case_id,
        "cancelled_index": first_cancelled["position"],
        "accepted_index": first_accepted["position"],
        "cancelled_seq": first_cancelled["seq"],
        "accepted_seq": first_accepted["seq"],
        "cancelled_activity": first_cancelled["activity"],
        "accepted_activity": first_accepted["activity"],
        "cancelled_timestamp": first_cancelled["timestamp"],
        "accepted_timestamp": first_accepted["timestamp"],
        "cancelled_event": first_cancelled,
        "accepted_event": first_accepted,
        "evidence_positions": [
            first_cancelled["position"],
            first_accepted["position"],
        ],
        "trace_length": len(events),
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
        for pos, event in enumerate(trace):
            if "concept:name" not in event or _is_missing(event.get("concept:name")):
                raise ValueError(
                    f"Event posisi {pos} pada case '{case_id}' tidak memiliki atribut wajib 'concept:name'."
                )
            if "time:timestamp" not in event or _is_missing(event.get("time:timestamp")):
                raise ValueError(
                    f"Event posisi {pos} pada case '{case_id}' tidak memiliki atribut wajib 'time:timestamp'."
                )

            case_events.append(
                _build_event_snapshot(
                    position=pos,
                    activity=event.get("concept:name"),
                    timestamp=event.get("time:timestamp"),
                    lifecycle=event.get("lifecycle:transition"),
                    resource=event.get("org:resource"),
                )
            )
        cases.append((case_id, case_events))

    return cases


def _extract_cases_from_dataframe(df: pd.DataFrame) -> list[tuple[Any, list[dict[str, Any]]]]:
    """Validate and group ordered case event sequences from a PM4Py DataFrame."""

    if len(df) == 0:
        return []

    columns = [str(col) for col in df.columns]
    col_index = {col: idx for idx, col in enumerate(columns)}
    missing_cols = [col for col in REQUIRED_DF_COLUMNS if col not in col_index]
    if missing_cols:
        raise ValueError(
            "DataFrame tidak memiliki kolom wajib: " + ", ".join(missing_cols)
        )

    case_idx = col_index["case:concept:name"]
    act_idx = col_index["concept:name"]
    ts_idx = col_index["time:timestamp"]
    lc_idx = col_index.get("lifecycle:transition")
    res_idx = col_index.get("org:resource")

    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row_num, row in enumerate(df.itertuples(index=False, name=None)):
        case_id = row[case_idx]
        if _is_missing(case_id):
            raise ValueError(
                f"Baris {row_num} tidak memiliki nilai wajib 'case:concept:name'."
            )

        activity = row[act_idx]
        if _is_missing(activity):
            raise ValueError(
                f"Baris {row_num} pada case '{case_id}' tidak memiliki nilai wajib 'concept:name'."
            )

        timestamp = row[ts_idx]
        if _is_missing(timestamp):
            raise ValueError(
                f"Baris {row_num} pada case '{case_id}' tidak memiliki nilai wajib 'time:timestamp'."
            )

        case_events = grouped.setdefault(case_id, [])
        pos = len(case_events)
        case_events.append(
            _build_event_snapshot(
                position=pos,
                activity=activity,
                timestamp=timestamp,
                lifecycle=row[lc_idx] if lc_idx is not None else None,
                resource=row[res_idx] if res_idx is not None else None,
            )
        )

    return list(grouped.items())


def analyze_1122(
    log_or_df: EventLog | pd.DataFrame,
    *,
    cancelled_activity: str = DEFAULT_CANCELLED_ACTIVITY,
    accepted_activity: str = DEFAULT_ACCEPTED_ACTIVITY,
) -> dict[str, Any]:
    """Run Exercise 11.22 analysis on an active PM4Py EventLog or DataFrame.

    Parameters
    ----------
    log_or_df:
        Active in-memory PM4Py ``EventLog`` or PM4Py ``DataFrame``.
    cancelled_activity:
        Activity name representing cancellation (default ``"O_Cancelled"``).
    accepted_activity:
        Activity name representing acceptance (default ``"O_Accepted"``).

    Returns
    -------
    dict[str, Any]
        Dictionary containing ``exercise``, ``rule``, ``cancelled_activity``,
        ``accepted_activity``, ``count``, ``total_cases``, ``percentage``,
        ``case_ids``, and ``evidence``.
    """

    if log_or_df is None:
        raise ValueError("Dataset belum dimuat (log_or_df bernilai None).")

    if isinstance(log_or_df, EventLog):
        cases = _extract_cases_from_event_log(log_or_df)
    elif hasattr(log_or_df, "columns") and hasattr(log_or_df, "itertuples"):
        cases = _extract_cases_from_dataframe(log_or_df)
    else:
        raise TypeError(
            "Input harus berupa PM4Py EventLog atau DataFrame PM4Py."
        )

    total_cases = len(cases)
    case_ids: list[Any] = []
    evidence: list[dict[str, Any]] = []

    for case_id, events in cases:
        match = _evaluate_case_events(
            case_id, events, cancelled_activity, accepted_activity
        )
        if match is not None:
            case_ids.append(case_id)
            evidence.append(match)

    count = len(case_ids)
    percentage = (count / total_cases * 100.0) if total_cases > 0 else 0.0

    return {
        "exercise": "11.22",
        "rule": RULE_DESCRIPTION,
        "cancelled_activity": cancelled_activity,
        "accepted_activity": accepted_activity,
        "count": count,
        "total_cases": total_cases,
        "percentage": percentage,
        "case_ids": case_ids,
        "evidence": evidence,
    }

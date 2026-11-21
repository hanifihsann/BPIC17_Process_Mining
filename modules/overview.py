"""Overview calculations for a PM4Py event log.

The public function in this module works on an already-loaded EventLog. It
does not load an XES file or mutate the supplied log.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from pm4py.objects.log.obj import EventLog


def _is_missing(value: Any) -> bool:
    """Return whether a scalar value is null-like."""

    if value is None:
        return True
    try:
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False
    except Exception:
        return False


def _parse_timestamp(value: Any) -> pd.Timestamp | None:
    """Parse one timestamp without changing the source value."""

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


def _empty_overview() -> dict[str, Any]:
    """Return the stable shape used for overview results."""

    return {
        "case_count": 0,
        "event_count": 0,
        "activity_frequency": {},
        "time_range": {"start": None, "end": None},
        "mean_cycle_time_days": None,
        "cycle_time_case_count": 0,
        "case_durations": [],
        "skipped_cases": [],
        "errors": [],
    }


def _add_case_duration(
    result: dict[str, Any],
    case_id: Any,
    first_timestamp: pd.Timestamp | None,
    last_timestamp: pd.Timestamp | None,
    reason_if_invalid: str,
) -> None:
    """Append one duration record or one reason for skipping it."""

    if first_timestamp is None or last_timestamp is None:
        result["skipped_cases"].append(
            {"case_id": case_id, "reason": reason_if_invalid}
        )
        return

    duration = last_timestamp - first_timestamp
    if not isinstance(duration, timedelta):
        duration = timedelta(seconds=duration.total_seconds())

    result["case_durations"].append(
        {
            "case_id": case_id,
            "start_timestamp": first_timestamp,
            "end_timestamp": last_timestamp,
            "duration": duration,
            "duration_days": duration.total_seconds() / 86400,
        }
    )


def _finalize_result(
    result: dict[str, Any],
    computed_case_count: int,
    computed_event_count: int,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply compatible metadata counts and calculate the mean duration."""

    result["case_count"] = computed_case_count
    result["event_count"] = computed_event_count

    if metadata is not None:
        metadata_case_count = metadata.get("case_count")
        metadata_event_count = metadata.get("event_count")
        if metadata_case_count == computed_case_count:
            result["case_count"] = metadata_case_count
        if metadata_event_count == computed_event_count:
            result["event_count"] = metadata_event_count

    durations = result["case_durations"]
    result["cycle_time_case_count"] = len(durations)
    if durations:
        result["mean_cycle_time_days"] = sum(
            row["duration_days"] for row in durations
        ) / len(durations)

    return result


def _calculate_event_log_overview(
    log: EventLog, metadata: dict[str, Any] | None
) -> dict[str, Any]:
    """Calculate an overview in one main pass over an EventLog."""

    result = _empty_overview()
    activity_frequency: dict[Any, int] = {}
    global_start: pd.Timestamp | None = None
    global_end: pd.Timestamp | None = None
    computed_event_count = 0

    for trace in log:
        case_id = trace.attributes.get("concept:name")
        if _is_missing(case_id):
            case_id = None

        if not trace:
            result["skipped_cases"].append(
                {"case_id": case_id, "reason": "empty trace"}
            )
            continue

        first_timestamp = _parse_timestamp(trace[0].get("time:timestamp"))
        last_timestamp: pd.Timestamp | None = None

        for event in trace:
            computed_event_count += 1
            activity = event.get("concept:name")
            if not _is_missing(activity):
                activity_frequency[activity] = activity_frequency.get(activity, 0) + 1

            timestamp = _parse_timestamp(event.get("time:timestamp"))
            last_timestamp = timestamp
            if timestamp is not None:
                if global_start is None or timestamp < global_start:
                    global_start = timestamp
                if global_end is None or timestamp > global_end:
                    global_end = timestamp

        _add_case_duration(
            result,
            case_id,
            first_timestamp,
            last_timestamp,
            "first or last event has an invalid timestamp",
        )

    result["activity_frequency"] = activity_frequency
    result["time_range"] = {"start": global_start, "end": global_end}
    return _finalize_result(result, len(log), computed_event_count, metadata)


def _calculate_dataframe_overview(
    dataframe: Any, metadata: dict[str, Any] | None
) -> dict[str, Any]:
    """Calculate an overview for a PM4Py dataframe representation."""

    result = _empty_overview()
    required_columns = {
        "case:concept:name",
        "concept:name",
        "time:timestamp",
    }
    columns = {str(column) for column in dataframe.columns}
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        result["errors"].append(
            "Missing required dataframe columns: " + ", ".join(missing_columns)
        )
        return _finalize_result(result, 0, 0, metadata)

    case_states: dict[Any, dict[str, Any]] = {}
    activity_frequency: dict[Any, int] = {}
    global_start: pd.Timestamp | None = None
    global_end: pd.Timestamp | None = None

    column_list = list(dataframe.columns)
    column_index = {str(column): index for index, column in enumerate(column_list)}
    missing_case_number = 0

    for row in dataframe.itertuples(index=False, name=None):
        case_id = row[column_index["case:concept:name"]]
        if _is_missing(case_id):
            case_id = None
            case_key = ("__missing_case__", missing_case_number)
            missing_case_number += 1
        else:
            case_key = case_id

        state = case_states.setdefault(
            case_key,
            {
                "case_id": case_id,
                "first_timestamp": None,
                "last_timestamp": None,
                "first_seen": False,
            },
        )

        activity = row[column_index["concept:name"]]
        if not _is_missing(activity):
            activity_frequency[activity] = activity_frequency.get(activity, 0) + 1

        timestamp = _parse_timestamp(row[column_index["time:timestamp"]])
        if not state["first_seen"]:
            state["first_timestamp"] = timestamp
            state["first_seen"] = True
        state["last_timestamp"] = timestamp

        if timestamp is not None:
            if global_start is None or timestamp < global_start:
                global_start = timestamp
            if global_end is None or timestamp > global_end:
                global_end = timestamp

    for state in case_states.values():
        _add_case_duration(
            result,
            state["case_id"],
            state["first_timestamp"],
            state["last_timestamp"],
            "first or last row has an invalid timestamp",
        )

    result["activity_frequency"] = activity_frequency
    result["time_range"] = {"start": global_start, "end": global_end}
    return _finalize_result(result, len(case_states), len(dataframe), metadata)


def calculate_overview(
    log_or_df: EventLog | Any, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Calculate dataset-level metrics from an already-loaded object.

    For an EventLog, case durations use the first and last event in each
    original trace order; events are never sorted or removed. Empty traces and
    traces whose first or last timestamp cannot be parsed are listed in
    ``skipped_cases`` and excluded from the cycle-time mean. Each item in
    ``case_durations`` contains ``case_id``, ``start_timestamp``,
    ``end_timestamp``, ``duration`` as a ``timedelta``, and ``duration_days``.

    ``metadata`` is optional. Its case/event counts are used only when they
    match the counts computed from the active object. It is never used to
    reload or revalidate the XES file.
    """

    if isinstance(log_or_df, EventLog):
        return _calculate_event_log_overview(log_or_df, metadata)

    if hasattr(log_or_df, "columns") and hasattr(log_or_df, "itertuples"):
        return _calculate_dataframe_overview(log_or_df, metadata)

    result = _empty_overview()
    result["errors"].append(
        "Input harus berupa PM4Py EventLog atau dataframe PM4Py."
    )
    return result

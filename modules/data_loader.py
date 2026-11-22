"""Utilities for loading and validating BPIC17 XES event logs.

The loader keeps the PM4Py ``EventLog`` object intact so other modules can
reuse the same in-memory log instead of reading the XES file again.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pm4py
from pm4py.objects.log.obj import EventLog


REQUIRED_TRACE_ATTRIBUTES = ("concept:name",)
REQUIRED_EVENT_ATTRIBUTES = ("concept:name", "time:timestamp")
OPTIONAL_EVENT_ATTRIBUTES = ("lifecycle:transition", "org:resource")


def _empty_validation_result() -> dict[str, Any]:
    """Return the common shape used by :func:`validate_log`."""

    return {
        "valid": False,
        "log_type": None,
        "case_count": 0,
        "event_count": 0,
        "available_trace_attributes": [],
        "available_event_attributes": [],
        "required_attributes": {
            "trace": list(REQUIRED_TRACE_ATTRIBUTES),
            "event": list(REQUIRED_EVENT_ATTRIBUTES),
        },
        "missing_required_attributes": {"trace": [], "event": []},
        "optional_attributes": {
            name: False for name in OPTIONAL_EVENT_ATTRIBUTES
        },
        "missing_value_counts": {
            "trace:concept:name": 0,
            "concept:name": 0,
            "time:timestamp": 0,
        },
        "invalid_value_counts": {
            "time:timestamp": 0,
        },
        "errors": [],
    }


def _is_missing(value: Any) -> bool:
    """Return whether an attribute value is absent.

    This deliberately avoids importing pandas.  It handles the values that
    occur in PM4Py event logs and also works for common dataframe null values.
    """

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()

    try:
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False
    except Exception:
        return False


def _is_valid_timestamp(value: Any) -> bool:
    """Return whether one non-null value can be parsed as a datetime.

    Parsing is used only for validation.  The original value in the log or
    dataframe is never replaced or modified.
    """

    if _is_missing(value):
        return False

    # PM4Py normally returns pandas.Timestamp values from XES.  They are
    # already parsed, so avoid reparsing every event in a large log.
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return True

    try:
        parsed = pd.to_datetime(value, errors="coerce")
        return not bool(pd.isna(parsed))
    except (TypeError, ValueError, OverflowError):
        return False


def _validate_event_log(log: EventLog) -> dict[str, Any]:
    """Validate a PM4Py legacy ``EventLog`` without reading the source file."""

    result = _empty_validation_result()
    result["log_type"] = type(log).__name__
    result["case_count"] = len(log)

    trace_attributes: set[str] = set()
    event_attributes: set[str] = set()
    seen_ids = set()
    duplicate_ids = 0
    missing_case_ids = 0
    missing_activity = 0
    missing_timestamp = 0
    invalid_timestamp = 0

    for trace in log:
        trace_attributes.update(str(key) for key in trace.attributes.keys())
        case_id = trace.attributes.get("concept:name")
        if _is_missing(case_id):
            missing_case_ids += 1
        elif case_id in seen_ids:
            duplicate_ids += 1
        else:
            seen_ids.add(case_id)

        for event in trace:
            result["event_count"] += 1
            event_attributes.update(str(key) for key in event.keys())
            if _is_missing(event.get("concept:name")):
                missing_activity += 1
            if _is_missing(event.get("time:timestamp")):
                missing_timestamp += 1
            elif not _is_valid_timestamp(event.get("time:timestamp")):
                invalid_timestamp += 1

    result["available_trace_attributes"] = sorted(trace_attributes)
    result["available_event_attributes"] = sorted(event_attributes)
    result["missing_value_counts"] = {
        "trace:concept:name": missing_case_ids,
        "concept:name": missing_activity,
        "time:timestamp": missing_timestamp,
    }
    result["invalid_value_counts"]["time:timestamp"] = invalid_timestamp
    result["missing_required_attributes"]["trace"] = [
        name
        for name in REQUIRED_TRACE_ATTRIBUTES
        if name not in trace_attributes
    ]
    result["missing_required_attributes"]["event"] = [
        name
        for name in REQUIRED_EVENT_ATTRIBUTES
        if name not in event_attributes
    ]
    result["optional_attributes"] = {
        name: name in event_attributes for name in OPTIONAL_EVENT_ATTRIBUTES
    }

    if missing_case_ids:
        result["errors"].append(
            f"{missing_case_ids} trace(s) tidak memiliki case ID 'concept:name'."
        )
    if duplicate_ids:
        result["invalid_value_counts"]["trace:concept:name"] = duplicate_ids
        result["errors"].append(
            f"{duplicate_ids} trace memiliki Case ID duplikat; setiap trace harus memiliki ID unik."
        )
    if missing_activity:
        result["errors"].append(
            f"{missing_activity} event tidak memiliki activity 'concept:name'."
        )
    if missing_timestamp:
        result["errors"].append(
            f"{missing_timestamp} event tidak memiliki timestamp 'time:timestamp'."
        )
    if invalid_timestamp:
        result["errors"].append(
            f"{invalid_timestamp} event memiliki timestamp 'time:timestamp' yang tidak valid."
        )

    result["valid"] = (
        result["case_count"] > 0
        and result["event_count"] > 0
        and not result["missing_required_attributes"]["trace"]
        and not result["missing_required_attributes"]["event"]
        and not result["errors"]
    )
    return result


def _validate_dataframe(log_or_df: Any) -> dict[str, Any]:
    """Validate a PM4Py dataframe representation.

    PM4Py uses ``case:concept:name`` for the trace identifier after converting
    an EventLog to a dataframe.  Event attributes retain their XES names.
    """

    result = _empty_validation_result()
    result["log_type"] = type(log_or_df).__name__
    columns = [str(column) for column in log_or_df.columns]
    column_set = set(columns)
    result["available_event_attributes"] = sorted(
        column for column in columns if not column.startswith("case:")
    )
    result["available_trace_attributes"] = sorted(
        column for column in columns if column.startswith("case:")
    )
    result["case_count"] = (
        int(log_or_df["case:concept:name"].nunique(dropna=True))
        if "case:concept:name" in column_set
        else 0
    )
    result["event_count"] = int(len(log_or_df))

    missing_case_ids = 0
    missing_activity = 0
    missing_timestamp = 0
    invalid_timestamp = 0

    if "case:concept:name" in column_set:
        missing_case_ids = sum(
            _is_missing(value) for value in log_or_df["case:concept:name"]
        )
    if "concept:name" in column_set:
        missing_activity = sum(
            _is_missing(value) for value in log_or_df["concept:name"]
        )
    if "time:timestamp" in column_set:
        for value in log_or_df["time:timestamp"]:
            if _is_missing(value):
                missing_timestamp += 1
            elif not _is_valid_timestamp(value):
                invalid_timestamp += 1

    result["missing_value_counts"] = {
        "trace:concept:name": missing_case_ids,
        "concept:name": missing_activity,
        "time:timestamp": missing_timestamp,
    }
    result["invalid_value_counts"]["time:timestamp"] = invalid_timestamp

    if "case:concept:name" not in column_set:
        result["missing_required_attributes"]["trace"].append("concept:name")
    if "concept:name" not in column_set:
        result["missing_required_attributes"]["event"].append("concept:name")
    if "time:timestamp" not in column_set:
        result["missing_required_attributes"]["event"].append("time:timestamp")

    for name in OPTIONAL_EVENT_ATTRIBUTES:
        result["optional_attributes"][name] = name in column_set

    if missing_case_ids:
        result["errors"].append(
            f"{missing_case_ids} baris tidak memiliki case ID 'case:concept:name'."
        )
    if missing_activity:
        result["errors"].append(
            f"{missing_activity} baris tidak memiliki activity 'concept:name'."
        )
    if missing_timestamp:
        result["errors"].append(
            f"{missing_timestamp} baris tidak memiliki timestamp 'time:timestamp'."
        )
    if invalid_timestamp:
        result["errors"].append(
            f"{invalid_timestamp} baris memiliki timestamp 'time:timestamp' yang tidak valid."
        )

    result["valid"] = (
        result["case_count"] > 0
        and result["event_count"] > 0
        and not result["missing_required_attributes"]["trace"]
        and not result["missing_required_attributes"]["event"]
        and not result["errors"]
    )
    return result


def validate_log(log_or_df: Any) -> dict[str, Any]:
    """Validate a PM4Py ``EventLog`` or PM4Py dataframe.

    The returned dictionary reports required and optional attributes, counts,
    and any missing values.  Validation uses the object supplied by the
    caller; it never reads the XES file.
    """

    if isinstance(log_or_df, EventLog):
        return _validate_event_log(log_or_df)

    if hasattr(log_or_df, "columns") and hasattr(log_or_df, "__len__"):
        return _validate_dataframe(log_or_df)

    result = _empty_validation_result()
    result["errors"].append(
        "Input harus berupa PM4Py EventLog atau dataframe PM4Py."
    )
    return result


def _same_case_id(left: Any, right: Any) -> bool:
    """Compare case IDs safely, including null-like values."""

    if _is_missing(left) or _is_missing(right):
        return _is_missing(left) and _is_missing(right)
    try:
        comparison = left == right
        return bool(comparison) if not hasattr(comparison, "__len__") else False
    except Exception:
        return False


def _event_to_trace_record(event: Any) -> dict[str, Any]:
    """Create the public trace-record shape without changing the event."""

    return {
        "activity": event.get("concept:name"),
        "timestamp": event.get("time:timestamp"),
        "lifecycle": event.get("lifecycle:transition"),
        "resource": event.get("org:resource"),
    }


def get_case_trace(log_or_df: Any, case_id: Any) -> list[dict[str, Any]]:
    """Return the ordered event records for one case.

    The function accepts a PM4Py ``EventLog`` or a PM4Py dataframe with the
    ``case:concept:name``, ``concept:name``, and ``time:timestamp`` columns.
    Optional lifecycle and resource columns/attributes are returned as
    ``None`` when unavailable. The source object is not sorted, filtered, or
    modified, and the XES file is never read by this helper.
    """

    if isinstance(log_or_df, EventLog):
        for trace in log_or_df:
            trace_case_id = trace.attributes.get("concept:name")
            if _same_case_id(trace_case_id, case_id):
                return [_event_to_trace_record(event) for event in trace]
        return []

    if hasattr(log_or_df, "columns") and hasattr(log_or_df, "itertuples"):
        columns = [str(column) for column in log_or_df.columns]
        column_index = {column: index for index, column in enumerate(columns)}
        case_column = "case:concept:name"
        if case_column not in column_index:
            return []

        activity_index = column_index.get("concept:name")
        timestamp_index = column_index.get("time:timestamp")
        lifecycle_index = column_index.get("lifecycle:transition")
        resource_index = column_index.get("org:resource")
        records: list[dict[str, Any]] = []

        for row in log_or_df.itertuples(index=False, name=None):
            if not _same_case_id(row[column_index[case_column]], case_id):
                continue
            records.append(
                {
                    "activity": (
                        row[activity_index] if activity_index is not None else None
                    ),
                    "timestamp": (
                        row[timestamp_index] if timestamp_index is not None else None
                    ),
                    "lifecycle": (
                        row[lifecycle_index] if lifecycle_index is not None else None
                    ),
                    "resource": (
                        row[resource_index] if resource_index is not None else None
                    ),
                }
            )
        return records

    return []


def load_xes(file_path: str | Path) -> tuple[EventLog, dict[str, Any]]:
    """Read an XES file with PM4Py and return ``(EventLog, metadata)``.

    ``FileNotFoundError`` is raised for a missing path, ``ValueError`` for a
    non-XES extension or directory, and ``RuntimeError`` when PM4Py cannot
    read the file.  The returned metadata contains validation information and
    dataset-level counts without performing a second file read.
    """

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File XES tidak ditemukan: {path}")
    if not path.is_file():
        raise ValueError(f"Path bukan file: {path}")
    if path.suffix.lower() != ".xes":
        raise ValueError(f"File harus memiliki ekstensi .xes: {path.name}")

    try:
        log = pm4py.read_xes(
            str(path),
            return_legacy_log_object=True,
        )
    except Exception as error:
        raise RuntimeError(f"Gagal membaca file XES '{path}': {error}") from error

    if not isinstance(log, EventLog):
        raise RuntimeError(
            "PM4Py tidak mengembalikan objek EventLog seperti yang diharapkan."
        )

    validation = validate_log(log)
    metadata = {
        "file_path": str(path.resolve()),
        "file_name": path.name,
        "extension": path.suffix.lower(),
        "case_count": validation["case_count"],
        "event_count": validation["event_count"],
        "available_trace_attributes": validation["available_trace_attributes"],
        "available_event_attributes": validation["available_event_attributes"],
        "validation": validation,
    }
    return log, metadata

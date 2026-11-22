"""Repeated-completion analyses for Exercises 11.15 and 11.18.

The analyses use an already-loaded PM4Py EventLog or PM4Py-style DataFrame.
Activity matching for ``W_Assess Potential Fraud`` ignores letter case, and only
events with lifecycle ``complete`` count.
Exercise 11.18 additionally groups those events by a non-empty resource ID.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

import pandas as pd
from pm4py.objects.log.obj import EventLog


DEFAULT_ACTIVITY = "W_Assess Potential Fraud"
COMPLETE_LIFECYCLE = "complete"
REQUIRED_DF_COLUMNS = ("case:concept:name", "concept:name", "time:timestamp")

RULE_1115 = (
    f"Case memiliki minimal dua event {DEFAULT_ACTIVITY} dengan "
    "lifecycle:transition = complete."
)
RULE_1118 = (
    f"Case memiliki minimal dua event {DEFAULT_ACTIVITY} berstatus complete "
    "dengan org:resource yang sama dan teridentifikasi."
)


def _is_missing(value: Any) -> bool:
    """Return whether a scalar is null-like, including pandas null values."""

    if value is None:
        return True
    try:
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False
    except Exception:
        return False


def _clean_optional(value: Any) -> Any:
    return None if _is_missing(value) else value


def _is_complete(value: Any) -> bool:
    if _is_missing(value):
        return False
    return isinstance(value, str) and value.strip().casefold() == COMPLETE_LIFECYCLE


def _is_target_activity(value: Any, activity: str) -> bool:
    """Compare activity names without treating capitalization as meaningful."""

    return (
        isinstance(value, str)
        and value.strip().casefold() == activity.strip().casefold()
    )


def _resource_key(value: Any) -> Hashable | None:
    """Return a grouping key for an identified resource, or None if absent."""

    if _is_missing(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        hash(value)
    except TypeError:
        # XES resource IDs are scalar. Malformed, non-scalar values cannot
        # establish that two events were performed by the same resource.
        return None
    # Include the type so values such as integer 1 and string "1" stay distinct.
    return (type(value), value)


def _snapshot(
    *,
    case_id: Any,
    position: int,
    activity: Any,
    lifecycle: Any,
    resource: Any,
    timestamp: Any,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "position": position,
        "seq": position + 1,
        "activity": activity,
        "lifecycle": _clean_optional(lifecycle),
        "resource": _clean_optional(resource),
        "timestamp": _clean_optional(timestamp),
    }


def _extract_event_log(
    log: EventLog, activity: str
) -> tuple[list[dict[str, Any]], bool, bool]:
    cases: list[dict[str, Any]] = []
    lifecycle_available = False
    resource_available = False

    for trace_idx, trace in enumerate(log):
        case_id = trace.attributes.get("concept:name")
        if _is_missing(case_id):
            raise ValueError(
                f"Trace indeks {trace_idx} tidak memiliki Case ID 'concept:name'."
            )

        occurrences: list[dict[str, Any]] = []
        for position, event in enumerate(trace):
            if "concept:name" not in event or _is_missing(event.get("concept:name")):
                raise ValueError(
                    f"Event posisi {position} pada case '{case_id}' tidak memiliki activity 'concept:name'."
                )
            if "time:timestamp" not in event or _is_missing(event.get("time:timestamp")):
                raise ValueError(
                    f"Event posisi {position} pada case '{case_id}' tidak memiliki timestamp 'time:timestamp'."
                )

            lifecycle_available |= "lifecycle:transition" in event
            resource_available |= "org:resource" in event
            lifecycle = event.get("lifecycle:transition")
            if _is_target_activity(
                event.get("concept:name"), activity
            ) and _is_complete(lifecycle):
                occurrences.append(
                    _snapshot(
                        case_id=case_id,
                        position=position,
                        activity=event.get("concept:name"),
                        lifecycle=lifecycle,
                        resource=event.get("org:resource"),
                        timestamp=event.get("time:timestamp"),
                    )
                )
        cases.append({"case_id": case_id, "occurrences": occurrences})

    return cases, lifecycle_available, resource_available


def _extract_dataframe(
    dataframe: pd.DataFrame, activity: str
) -> tuple[list[dict[str, Any]], bool, bool]:
    columns = [str(column) for column in dataframe.columns]
    column_index = {column: index for index, column in enumerate(columns)}

    if dataframe.empty:
        return (
            [],
            "lifecycle:transition" in column_index,
            "org:resource" in column_index,
        )

    missing_columns = [
        column for column in REQUIRED_DF_COLUMNS if column not in column_index
    ]
    if missing_columns:
        raise ValueError(
            "DataFrame tidak memiliki kolom wajib PM4Py: "
            + ", ".join(missing_columns)
            + "."
        )

    case_idx = column_index["case:concept:name"]
    activity_idx = column_index["concept:name"]
    timestamp_idx = column_index["time:timestamp"]
    lifecycle_idx = column_index.get("lifecycle:transition")
    resource_idx = column_index.get("org:resource")

    cases_by_id: dict[Any, dict[str, Any]] = {}
    event_positions: dict[Any, int] = {}

    for row_num, row in enumerate(dataframe.itertuples(index=False, name=None)):
        case_id = row[case_idx]
        if _is_missing(case_id):
            raise ValueError(
                f"Baris {row_num} tidak memiliki Case ID 'case:concept:name'."
            )

        event_activity = row[activity_idx]
        if _is_missing(event_activity):
            raise ValueError(
                f"Baris {row_num} pada case '{case_id}' tidak memiliki activity 'concept:name'."
            )
        timestamp = row[timestamp_idx]
        if _is_missing(timestamp):
            raise ValueError(
                f"Baris {row_num} pada case '{case_id}' tidak memiliki timestamp 'time:timestamp'."
            )

        state = cases_by_id.setdefault(
            case_id, {"case_id": case_id, "occurrences": []}
        )
        position = event_positions.get(case_id, 0)
        event_positions[case_id] = position + 1
        lifecycle = row[lifecycle_idx] if lifecycle_idx is not None else None
        resource = row[resource_idx] if resource_idx is not None else None

        if _is_target_activity(
            event_activity, activity
        ) and _is_complete(lifecycle):
            state["occurrences"].append(
                _snapshot(
                    case_id=case_id,
                    position=position,
                    activity=event_activity,
                    lifecycle=lifecycle,
                    resource=resource,
                    timestamp=timestamp,
                )
            )

    return (
        list(cases_by_id.values()),
        lifecycle_idx is not None,
        resource_idx is not None,
    )


def _analyze_1115(
    cases: list[dict[str, Any]], activity: str
) -> dict[str, Any]:
    evidence = []
    for case in cases:
        occurrences = case["occurrences"]
        if len(occurrences) < 2:
            continue
        evidence.append(
            {
                "case_id": case["case_id"],
                "activity": activity,
                "occurrence_count": len(occurrences),
                "evidence_positions": [event["position"] for event in occurrences],
                "label": f"11.15 {activity} complete",
                "evidence_events": occurrences,
            }
        )

    return {
        "subsoal": "11.15",
        "rule": (
            f"Case memiliki minimal dua event {activity} dengan "
            "lifecycle:transition = complete."
        ),
        "activity": activity,
        "count": len(evidence),
        "case_ids": [item["case_id"] for item in evidence],
        "evidence": evidence,
    }


def _analyze_1118(
    cases: list[dict[str, Any]], activity: str
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    qualifying_case_ids: list[Any] = []

    for case in cases:
        occurrences_by_resource: dict[Hashable, list[dict[str, Any]]] = {}
        resource_ids: dict[Hashable, Any] = {}
        for event in case["occurrences"]:
            resource = event["resource"]
            key = _resource_key(resource)
            if key is None:
                continue
            occurrences_by_resource.setdefault(key, []).append(event)
            resource_ids.setdefault(key, resource)

        case_has_match = False
        for key, occurrences in occurrences_by_resource.items():
            if len(occurrences) < 2:
                continue
            case_has_match = True
            resource_id = resource_ids[key]
            evidence.append(
                {
                    "case_id": case["case_id"],
                    "activity": activity,
                    "resource_id": resource_id,
                    "occurrence_count": len(occurrences),
                    "evidence_positions": [
                        event["position"] for event in occurrences
                    ],
                    "label": f"11.18 {activity} complete / {resource_id}",
                    "evidence_events": occurrences,
                }
            )
        if case_has_match:
            qualifying_case_ids.append(case["case_id"])

    return {
        "subsoal": "11.18",
        "rule": (
            f"Case memiliki minimal dua event {activity} berstatus complete "
            "dengan org:resource yang sama dan teridentifikasi."
        ),
        "activity": activity,
        "count": len(qualifying_case_ids),
        "case_ids": qualifying_case_ids,
        "evidence": evidence,
        "evidence_group_count": len(evidence),
    }


def analyze_115_118(
    log_or_df: Any,
    *,
    activity: str = DEFAULT_ACTIVITY,
) -> dict[str, Any]:
    """Analyze repeated complete occurrences for Exercises 11.15 and 11.18.

    Exercise 11.15 counts a case once when it contains at least two matching
    complete events. Activity names match without case sensitivity.
    Exercise 11.18 counts distinct cases with at least one
    identified resource responsible for at least two matching complete events.
    A case can have more than one qualifying resource group; its case-level
    count remains one while ``evidence_group_count`` reports those groups.
    """

    if log_or_df is None:
        raise ValueError("Dataset belum dimuat (log_or_df bernilai None).")
    if not isinstance(activity, str) or not activity:
        raise ValueError("Nama activity harus berupa string yang tidak kosong.")

    if isinstance(log_or_df, EventLog):
        cases, lifecycle_available, resource_available = _extract_event_log(
            log_or_df, activity
        )
    elif isinstance(log_or_df, pd.DataFrame):
        cases, lifecycle_available, resource_available = _extract_dataframe(
            log_or_df, activity
        )
    else:
        raise TypeError(
            "Input harus berupa PM4Py EventLog atau pandas DataFrame."
        )

    result_1115 = _analyze_1115(cases, activity)
    result_1118 = _analyze_1118(cases, activity)
    total_cases = len(cases)
    result_1115["total_cases"] = total_cases
    result_1118["total_cases"] = total_cases
    result_1115["lifecycle_attribute_available"] = lifecycle_available
    result_1118["lifecycle_attribute_available"] = lifecycle_available
    result_1118["resource_attribute_available"] = resource_available

    return {
        "exercise": "11.15 & 11.18",
        "activity": activity,
        "total_cases": total_cases,
        "lifecycle_attribute_available": lifecycle_available,
        "resource_attribute_available": resource_available,
        "11.15": result_1115,
        "11.18": result_1118,
    }

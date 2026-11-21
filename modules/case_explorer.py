"""Case Explorer module for inspecting full case traces and evidence markers.

Supports PM4Py ``EventLog`` and PM4Py ``pandas.DataFrame`` objects without
re-reading XES files or mutating the active dataset. Uses a lightweight,
weakref-managed index cache so repeated case lookups and searches avoid
repeated full-log scans.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
import weakref

import pandas as pd
from pm4py.objects.log.obj import EventLog

REQUIRED_DF_COLUMNS = ("case:concept:name", "concept:name", "time:timestamp")
OPTIONAL_EVENT_ATTRIBUTES = ("lifecycle:transition", "org:resource")


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


def _normalize_evidence_markers(
    evidence: Any = None,
    highlight_positions: Iterable[int] | None = None,
) -> dict[int, str]:
    """Normalize evidence/highlight inputs into ``{position_index: role_label}``."""

    markers: dict[int, str] = {}

    if highlight_positions is not None:
        for pos in highlight_positions:
            if isinstance(pos, int) and not isinstance(pos, bool) and pos >= 0:
                markers.setdefault(pos, "Evidence")

    if evidence is None:
        return markers

    if isinstance(evidence, Mapping):
        # Support Exercise 11.22 evidence records directly.
        cancelled_idx = evidence.get("cancelled_index")
        accepted_idx = evidence.get("accepted_index")
        if isinstance(cancelled_idx, int) and not isinstance(cancelled_idx, bool) and cancelled_idx >= 0:
            markers[cancelled_idx] = str(
                evidence.get("cancelled_activity") or "O_Cancelled"
            )
        if isinstance(accepted_idx, int) and not isinstance(accepted_idx, bool) and accepted_idx >= 0:
            markers[accepted_idx] = str(
                evidence.get("accepted_activity") or "O_Accepted"
            )

        # Support generic position lists/mappings for Exercises 11.7, 11.15, 11.18.
        for key in ("evidence_positions", "positions", "highlight_positions", "indices"):
            raw = evidence.get(key)
            if isinstance(raw, Mapping):
                for pos, label in raw.items():
                    if isinstance(pos, int) and not isinstance(pos, bool) and pos >= 0:
                        markers.setdefault(pos, str(label) if label else "Evidence")
            elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
                default_label = str(evidence.get("label") or "Evidence")
                for pos in raw:
                    if isinstance(pos, int) and not isinstance(pos, bool) and pos >= 0:
                        markers.setdefault(pos, default_label)

        # Support direct {int_position: label} dictionaries.
        for key, value in evidence.items():
            if isinstance(key, int) and not isinstance(key, bool) and key >= 0:
                markers[key] = str(value) if value else "Evidence"
        return markers

    if isinstance(evidence, Iterable) and not isinstance(evidence, (str, bytes)):
        for pos in evidence:
            if isinstance(pos, int) and not isinstance(pos, bool) and pos >= 0:
                markers.setdefault(pos, "Evidence")

    return markers


def _dataset_signature(log_or_df: Any) -> tuple[Any, ...]:
    """Compute a cheap structural signature to detect in-place length/column changes."""

    if isinstance(log_or_df, EventLog):
        first_id = id(log_or_df[0]) if len(log_or_df) > 0 else None
        last_id = id(log_or_df[-1]) if len(log_or_df) > 0 else None
        return ("event_log", len(log_or_df), first_id, last_id)

    columns = tuple(str(col) for col in log_or_df.columns)
    return ("dataframe", len(log_or_df), columns)


class CaseIndex:
    """In-memory lookup index for fast case listing, search, and trace retrieval."""

    def __init__(self, log_or_df: EventLog | pd.DataFrame) -> None:
        self.signature = _dataset_signature(log_or_df)
        self.source_type: str
        self.case_ids: list[Any] = []
        self.case_summaries: list[dict[str, Any]] = []
        self._summary_by_case_id: dict[Any, dict[str, Any]] = {}
        self._trace_pos_by_case_id: dict[Any, int] = {}
        self._df_rows_by_case_id: dict[Any, list[int]] = {}
        self._str_lookup: dict[str, list[Any]] = {}
        self._df_col_indices: dict[str, int] = {}

        if isinstance(log_or_df, EventLog):
            self.source_type = "event_log"
            self._build_event_log_index(log_or_df)
        elif hasattr(log_or_df, "columns") and hasattr(log_or_df, "itertuples"):
            self.source_type = "dataframe"
            self._build_dataframe_index(log_or_df)
        else:
            raise TypeError(
                "Input harus berupa PM4Py EventLog atau DataFrame PM4Py."
            )

    def matches(self, log_or_df: Any) -> bool:
        """Return True if this index still matches the dataset's structural signature."""

        return _dataset_signature(log_or_df) == self.signature

    def _register_case_id(self, case_id: Any) -> None:
        key_str = str(case_id)
        bucket = self._str_lookup.setdefault(key_str, [])
        if case_id not in bucket:
            bucket.append(case_id)

    def _build_event_log_index(self, log: EventLog) -> None:
        for trace_idx, trace in enumerate(log):
            case_id = trace.attributes.get("concept:name")
            if _is_missing(case_id):
                raise ValueError(
                    f"Trace indeks {trace_idx} tidak memiliki atribut wajib 'concept:name' (Case ID)."
                )

            for pos, event in enumerate(trace):
                if "concept:name" not in event or _is_missing(event.get("concept:name")):
                    raise ValueError(
                        f"Event posisi {pos} pada case '{case_id}' tidak memiliki atribut wajib 'concept:name'."
                    )
                if "time:timestamp" not in event or _is_missing(event.get("time:timestamp")):
                    raise ValueError(
                        f"Event posisi {pos} pada case '{case_id}' tidak memiliki atribut wajib 'time:timestamp'."
                    )

            if case_id not in self._trace_pos_by_case_id:
                self._trace_pos_by_case_id[case_id] = trace_idx
                self.case_ids.append(case_id)
                self._register_case_id(case_id)

                start_ts = trace[0].get("time:timestamp") if len(trace) > 0 else None
                end_ts = trace[-1].get("time:timestamp") if len(trace) > 0 else None
                summary = {
                    "case_id": case_id,
                    "event_count": len(trace),
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                }
                self.case_summaries.append(summary)
                self._summary_by_case_id[case_id] = summary

    def _build_dataframe_index(self, df: pd.DataFrame) -> None:
        columns = [str(col) for col in df.columns]
        col_index = {col: idx for idx, col in enumerate(columns)}
        self._df_col_indices = col_index

        if len(df) == 0 and len(columns) == 0:
            return

        missing_cols = [col for col in REQUIRED_DF_COLUMNS if col not in col_index]
        if missing_cols:
            raise ValueError(
                "DataFrame tidak memiliki kolom wajib: " + ", ".join(missing_cols)
            )

        if len(df) == 0:
            return

        case_idx = col_index["case:concept:name"]
        act_idx = col_index["concept:name"]
        ts_idx = col_index["time:timestamp"]

        start_ts_map: dict[Any, Any] = {}
        end_ts_map: dict[Any, Any] = {}

        for row_num, row in enumerate(df.itertuples(index=False, name=None)):
            case_id = row[case_idx]
            if _is_missing(case_id):
                raise ValueError(
                    f"Baris {row_num} tidak memiliki nilai wajib 'case:concept:name'."
                )
            if _is_missing(row[act_idx]):
                raise ValueError(
                    f"Baris {row_num} pada case '{case_id}' tidak memiliki nilai wajib 'concept:name'."
                )
            timestamp = row[ts_idx]
            if _is_missing(timestamp):
                raise ValueError(
                    f"Baris {row_num} pada case '{case_id}' tidak memiliki nilai wajib 'time:timestamp'."
                )

            if case_id not in self._df_rows_by_case_id:
                self._df_rows_by_case_id[case_id] = []
                self.case_ids.append(case_id)
                self._register_case_id(case_id)
                start_ts_map[case_id] = timestamp

            self._df_rows_by_case_id[case_id].append(row_num)
            end_ts_map[case_id] = timestamp

        for case_id in self.case_ids:
            row_indices = self._df_rows_by_case_id[case_id]
            summary = {
                "case_id": case_id,
                "event_count": len(row_indices),
                "start_timestamp": start_ts_map.get(case_id),
                "end_timestamp": end_ts_map.get(case_id),
            }
            self.case_summaries.append(summary)
            self._summary_by_case_id[case_id] = summary

    def resolve_case_id(self, case_id: Any) -> Any | None:
        """Resolve an exact or string-matched case ID if present in this index."""

        if _is_missing(case_id):
            return None

        if self.source_type == "event_log":
            if case_id in self._trace_pos_by_case_id:
                return case_id
        else:
            if case_id in self._df_rows_by_case_id:
                return case_id

        candidates = self._str_lookup.get(str(case_id), [])
        if len(candidates) == 1:
            return candidates[0]
        return None


_INDEX_CACHE: dict[int, tuple[CaseIndex, Any]] = {}


def _evict_cached_index(obj_id: int) -> None:
    _INDEX_CACHE.pop(obj_id, None)


def clear_case_index_cache() -> None:
    """Clear the internal weakref-managed CaseIndex cache."""

    _INDEX_CACHE.clear()


def build_case_index(log_or_df: EventLog | pd.DataFrame) -> CaseIndex:
    """Validate required attributes and build a fresh ``CaseIndex``."""

    if log_or_df is None:
        raise ValueError("Dataset belum dimuat (log_or_df bernilai None).")
    return CaseIndex(log_or_df)


def get_or_build_case_index(log_or_df: EventLog | pd.DataFrame) -> CaseIndex:
    """Return a cached ``CaseIndex`` for ``log_or_df`` or build one safely."""

    if log_or_df is None:
        raise ValueError("Dataset belum dimuat (log_or_df bernilai None).")

    obj_id = id(log_or_df)
    cached = _INDEX_CACHE.get(obj_id)
    if cached is not None:
        index_obj, _finalizer = cached
        if index_obj.matches(log_or_df):
            return index_obj

    index_obj = CaseIndex(log_or_df)
    try:
        finalizer = weakref.finalize(log_or_df, _evict_cached_index, obj_id)
        _INDEX_CACHE[obj_id] = (index_obj, finalizer)
    except TypeError:
        # Object does not support weak references; skip caching safely.
        pass
    return index_obj


def validate_required_attributes(log_or_df: EventLog | pd.DataFrame) -> bool:
    """Validate required attributes for Case Explorer and return True if valid."""

    get_or_build_case_index(log_or_df)
    return True


def list_cases(
    log_or_df: EventLog | pd.DataFrame,
    *,
    index: CaseIndex | None = None,
) -> list[dict[str, Any]]:
    """Return case summaries in original log order without mutating the dataset."""

    idx = index if index is not None else get_or_build_case_index(log_or_df)
    return [dict(summary) for summary in idx.case_summaries]


def search_cases(
    log_or_df: EventLog | pd.DataFrame,
    query: str = "",
    *,
    index: CaseIndex | None = None,
) -> list[dict[str, Any]]:
    """Filter cases by case-insensitive Case ID substring match."""

    idx = index if index is not None else get_or_build_case_index(log_or_df)
    normalized = "" if query is None else str(query).strip().casefold()
    if not normalized:
        return [dict(summary) for summary in idx.case_summaries]
    return [
        dict(summary)
        for summary in idx.case_summaries
        if normalized in str(summary["case_id"]).casefold()
    ]


def get_case_trace(
    log_or_df: EventLog | pd.DataFrame,
    case_id: Any,
    *,
    evidence: Any = None,
    highlight_positions: Iterable[int] | None = None,
    index: CaseIndex | None = None,
) -> list[dict[str, Any]]:
    """Return the complete ordered event trace for ``case_id``.

    Returns all events from the original case (never filtered), preserving the
    original event order. Each event dict contains ``seq`` (1-based),
    ``position`` (0-based), ``case_id``, ``timestamp``, ``activity``,
    ``lifecycle`` (or ``None``), ``resource`` (or ``None``), ``is_evidence``,
    and ``evidence_role``. Returns ``[]`` if ``case_id`` is not found.
    """

    idx = index if index is not None else get_or_build_case_index(log_or_df)
    resolved_id = idx.resolve_case_id(case_id)
    if resolved_id is None:
        return []

    markers = _normalize_evidence_markers(evidence, highlight_positions)
    records: list[dict[str, Any]] = []

    if idx.source_type == "event_log":
        trace_pos = idx._trace_pos_by_case_id[resolved_id]
        trace = log_or_df[trace_pos]
        for pos, event in enumerate(trace):
            role = markers.get(pos)
            records.append(
                {
                    "seq": pos + 1,
                    "position": pos,
                    "case_id": resolved_id,
                    "timestamp": event.get("time:timestamp"),
                    "activity": event.get("concept:name"),
                    "lifecycle": _clean_optional(event.get("lifecycle:transition")),
                    "resource": _clean_optional(event.get("org:resource")),
                    "is_evidence": pos in markers,
                    "evidence_role": role,
                }
            )
        return records

    row_indices = idx._df_rows_by_case_id[resolved_id]
    col_index = idx._df_col_indices
    act_col = col_index["concept:name"]
    ts_col = col_index["time:timestamp"]
    lc_col = col_index.get("lifecycle:transition")
    res_col = col_index.get("org:resource")

    subset = log_or_df.iloc[row_indices]
    for pos, row in enumerate(subset.itertuples(index=False, name=None)):
        role = markers.get(pos)
        records.append(
            {
                "seq": pos + 1,
                "position": pos,
                "case_id": resolved_id,
                "timestamp": row[ts_col],
                "activity": row[act_col],
                "lifecycle": _clean_optional(row[lc_col]) if lc_col is not None else None,
                "resource": _clean_optional(row[res_col]) if res_col is not None else None,
                "is_evidence": pos in markers,
                "evidence_role": role,
            }
        )
    return records


def get_case_detail(
    log_or_df: EventLog | pd.DataFrame,
    case_id: Any,
    *,
    evidence: Any = None,
    highlight_positions: Iterable[int] | None = None,
    index: CaseIndex | None = None,
) -> dict[str, Any]:
    """Return structured case metadata together with its full ordered trace."""

    idx = index if index is not None else get_or_build_case_index(log_or_df)
    resolved_id = idx.resolve_case_id(case_id)
    if resolved_id is None:
        return {
            "found": False,
            "case_id": case_id,
            "event_count": 0,
            "start_timestamp": None,
            "end_timestamp": None,
            "events": [],
            "evidence_positions": [],
        }

    events = get_case_trace(
        log_or_df,
        resolved_id,
        evidence=evidence,
        highlight_positions=highlight_positions,
        index=idx,
    )
    summary = idx._summary_by_case_id.get(resolved_id, {})
    return {
        "found": True,
        "case_id": resolved_id,
        "event_count": len(events),
        "start_timestamp": summary.get("start_timestamp"),
        "end_timestamp": summary.get("end_timestamp"),
        "events": events,
        "evidence_positions": [e["position"] for e in events if e["is_evidence"]],
    }

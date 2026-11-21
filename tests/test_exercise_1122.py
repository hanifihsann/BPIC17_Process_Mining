import unittest
from datetime import datetime, timezone

import pandas as pd
from pm4py.objects.log.obj import Event, EventLog, Trace

from modules.exercise_1122 import analyze_1122


def _make_event(
    activity: str,
    timestamp: datetime,
    lifecycle: str | None = None,
    resource: str | None = None,
    extra: dict | None = None,
) -> Event:
    payload = {
        "concept:name": activity,
        "time:timestamp": timestamp,
    }
    if lifecycle is not None:
        payload["lifecycle:transition"] = lifecycle
    if resource is not None:
        payload["org:resource"] = resource
    if extra:
        payload.update(extra)
    return Event(payload)


def _make_trace(case_id: str, events: list[Event]) -> Trace:
    return Trace(events, attributes={"concept:name": case_id})


def _to_pm4py_dataframe(log: EventLog) -> pd.DataFrame:
    """Convert a synthetic EventLog fixture into an equivalent PM4Py-style DataFrame."""

    rows = []
    for trace in log:
        case_id = trace.attributes.get("concept:name")
        for event in trace:
            row = {
                "case:concept:name": case_id,
                "concept:name": event.get("concept:name"),
                "time:timestamp": event.get("time:timestamp"),
            }
            if "lifecycle:transition" in event:
                row["lifecycle:transition"] = event["lifecycle:transition"]
            if "org:resource" in event:
                row["org:resource"] = event["org:resource"]
            rows.append(row)
    return pd.DataFrame(rows)


class Exercise1122Tests(unittest.TestCase):
    def test_cancelled_immediately_followed_by_accepted_passes(self):
        t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
        log = EventLog(
            [
                _make_trace(
                    "C1",
                    [
                        _make_event("O_Cancelled", t0, "complete", "User_1"),
                        _make_event("O_Accepted", t1, "complete", "User_2"),
                    ],
                )
            ]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["total_cases"], 1)
        self.assertAlmostEqual(result["percentage"], 100.0)
        self.assertEqual(result["case_ids"], ["C1"])
        self.assertEqual(len(result["evidence"]), 1)

        ev = result["evidence"][0]
        self.assertEqual(ev["case_id"], "C1")
        self.assertEqual(ev["cancelled_index"], 0)
        self.assertEqual(ev["accepted_index"], 1)
        self.assertEqual(ev["cancelled_activity"], "O_Cancelled")
        self.assertEqual(ev["accepted_activity"], "O_Accepted")
        self.assertEqual(ev["cancelled_timestamp"], t0)
        self.assertEqual(ev["accepted_timestamp"], t1)
        self.assertEqual(ev["evidence_positions"], [0, 1])

    def test_cancelled_with_intervening_activities_then_accepted_passes(self):
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 1, 9, 10, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 9, 20, tzinfo=timezone.utc)
        t3 = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
        log = EventLog(
            [
                _make_trace(
                    "C2",
                    [
                        _make_event("A_Create Application", t0),
                        _make_event("O_Cancelled", t1),
                        _make_event("O_Create Offer", t2),
                        _make_event("O_Accepted", t3),
                    ],
                )
            ]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["case_ids"], ["C2"])
        self.assertEqual(result["evidence"][0]["cancelled_index"], 1)
        self.assertEqual(result["evidence"][0]["accepted_index"], 3)

    def test_accepted_before_cancelled_without_subsequent_accepted_fails(self):
        t0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 1, 8, 5, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 8, 10, tzinfo=timezone.utc)
        log = EventLog(
            [
                _make_trace(
                    "C3",
                    [
                        _make_event("O_Accepted", t0),
                        _make_event("A_Validate", t1),
                        _make_event("O_Cancelled", t2),
                    ],
                )
            ]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total_cases"], 1)
        self.assertAlmostEqual(result["percentage"], 0.0)
        self.assertEqual(result["case_ids"], [])
        self.assertEqual(result["evidence"], [])

    def test_accepted_before_cancelled_followed_by_new_accepted_passes(self):
        t0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 1, 8, 5, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 8, 10, tzinfo=timezone.utc)
        log = EventLog(
            [
                _make_trace(
                    "C3b",
                    [
                        _make_event("O_Accepted", t0),
                        _make_event("O_Cancelled", t1),
                        _make_event("O_Accepted", t2),
                    ],
                )
            ]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["evidence"][0]["cancelled_index"], 1)
        self.assertEqual(result["evidence"][0]["accepted_index"], 2)

    def test_cancelled_only_does_not_pass(self):
        t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        log = EventLog(
            [_make_trace("C4", [_make_event("A_Submitted", t0), _make_event("O_Cancelled", t0)])]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["case_ids"], [])

    def test_accepted_only_does_not_pass(self):
        t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        log = EventLog(
            [_make_trace("C5", [_make_event("A_Submitted", t0), _make_event("O_Accepted", t0)])]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["case_ids"], [])

    def test_multiple_valid_pairs_in_one_case_counted_once(self):
        t = [datetime(2026, 1, 1, 10, m, tzinfo=timezone.utc) for m in range(5)]
        log = EventLog(
            [
                _make_trace(
                    "C6",
                    [
                        _make_event("O_Cancelled", t[0], extra={"OfferID": "Offer_1"}),
                        _make_event("O_Accepted", t[1], extra={"OfferID": "Offer_2"}),
                        _make_event("O_Cancelled", t[2], extra={"OfferID": "Offer_2"}),
                        _make_event("O_Accepted", t[3], extra={"OfferID": "Offer_3"}),
                    ],
                )
            ]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["total_cases"], 1)
        self.assertAlmostEqual(result["percentage"], 100.0)
        self.assertEqual(result["case_ids"], ["C6"])
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["evidence"][0]["cancelled_index"], 0)
        self.assertEqual(result["evidence"][0]["accepted_index"], 1)

    def test_multiple_cases_percentage_and_denominator_correct(self):
        t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
        log = EventLog(
            [
                _make_trace("Case_A", [_make_event("O_Cancelled", t0), _make_event("O_Accepted", t1)]),
                _make_trace("Case_B", [_make_event("O_Accepted", t0), _make_event("O_Cancelled", t1)]),
                _make_trace("Case_C", [_make_event("A_Create Application", t0), _make_event("O_Cancelled", t0), _make_event("W_Complete", t1), _make_event("O_Accepted", t1)]),
                _make_trace("Case_D", [_make_event("A_Create Application", t0)]),
            ]
        )

        result = analyze_1122(log)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["total_cases"], 4)
        self.assertAlmostEqual(result["percentage"], 50.0)
        self.assertEqual(result["case_ids"], ["Case_A", "Case_C"])
        self.assertIn("O_Cancelled", result["rule"])
        self.assertIn("O_Accepted", result["rule"])

    def test_empty_dataset_is_safe_without_zero_division(self):
        empty_log = EventLog([])
        res_log = analyze_1122(empty_log)
        self.assertEqual(res_log["count"], 0)
        self.assertEqual(res_log["total_cases"], 0)
        self.assertEqual(res_log["percentage"], 0.0)
        self.assertEqual(res_log["case_ids"], [])
        self.assertEqual(res_log["evidence"], [])

        empty_df = pd.DataFrame(
            columns=["case:concept:name", "concept:name", "time:timestamp"]
        )
        res_df = analyze_1122(empty_df)
        self.assertEqual(res_df["count"], 0)
        self.assertEqual(res_df["total_cases"], 0)
        self.assertEqual(res_df["percentage"], 0.0)

        bare_df = pd.DataFrame()
        res_bare = analyze_1122(bare_df)
        self.assertEqual(res_bare["total_cases"], 0)
        self.assertEqual(res_bare["percentage"], 0.0)

    def test_equal_timestamps_preserve_original_trace_order(self):
        same_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        log = EventLog(
            [
                _make_trace(
                    "SameTS_Pass",
                    [
                        _make_event("O_Cancelled", same_ts),
                        _make_event("O_Accepted", same_ts),
                    ],
                ),
                _make_trace(
                    "SameTS_Fail",
                    [
                        _make_event("O_Accepted", same_ts),
                        _make_event("O_Cancelled", same_ts),
                    ],
                ),
            ]
        )
        before_order = [[e["concept:name"] for e in tr] for tr in log]

        result = analyze_1122(log)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["total_cases"], 2)
        self.assertEqual(result["case_ids"], ["SameTS_Pass"])
        self.assertAlmostEqual(result["percentage"], 50.0)
        self.assertEqual([[e["concept:name"] for e in tr] for tr in log], before_order)

    def test_event_log_and_dataframe_produce_equivalent_results(self):
        t = [datetime(2026, 2, 1, h, 0, tzinfo=timezone.utc) for h in range(6)]
        log = EventLog(
            [
                _make_trace(
                    "Case_1",
                    [
                        _make_event("A_Create Application", t[0], "complete", "User_1"),
                        _make_event("O_Cancelled", t[1], "complete", "User_2"),
                        _make_event("O_Create Offer", t[2], "complete", "User_2"),
                        _make_event("O_Accepted", t[3], "complete", "User_3"),
                    ],
                ),
                _make_trace(
                    "Case_2",
                    [
                        _make_event("O_Accepted", t[0], "complete", "User_1"),
                        _make_event("O_Cancelled", t[1], "complete", "User_1"),
                    ],
                ),
                _make_trace(
                    "Case_3",
                    [
                        _make_event("O_Cancelled", t[4], "complete", "User_4"),
                        _make_event("O_Cancelled", t[4], "complete", "User_4"),
                        _make_event("O_Accepted", t[5], "complete", "User_5"),
                    ],
                ),
            ]
        )
        df = _to_pm4py_dataframe(log)

        res_log = analyze_1122(log)
        res_df = analyze_1122(df)

        self.assertEqual(res_log["count"], res_df["count"])
        self.assertEqual(res_log["total_cases"], res_df["total_cases"])
        self.assertAlmostEqual(res_log["percentage"], res_df["percentage"])
        self.assertEqual(res_log["case_ids"], res_df["case_ids"])
        self.assertEqual(len(res_log["evidence"]), len(res_df["evidence"]))

        for ev_log, ev_df in zip(res_log["evidence"], res_df["evidence"]):
            self.assertEqual(ev_log["case_id"], ev_df["case_id"])
            self.assertEqual(ev_log["cancelled_index"], ev_df["cancelled_index"])
            self.assertEqual(ev_log["accepted_index"], ev_df["accepted_index"])
            self.assertEqual(ev_log["cancelled_activity"], ev_df["cancelled_activity"])
            self.assertEqual(ev_log["accepted_activity"], ev_df["accepted_activity"])
            self.assertEqual(ev_log["cancelled_timestamp"], ev_df["cancelled_timestamp"])
            self.assertEqual(ev_log["accepted_timestamp"], ev_df["accepted_timestamp"])

    def test_missing_required_attributes_raise_value_error(self):
        bad_log = EventLog([Trace([Event({"concept:name": "O_Cancelled"})], attributes={"concept:name": "C_Bad"})])
        with self.assertRaises(ValueError):
            analyze_1122(bad_log)

        bad_df = pd.DataFrame({"case:concept:name": ["C1"], "concept:name": ["O_Cancelled"]})
        with self.assertRaises(ValueError):
            analyze_1122(bad_df)


if __name__ == "__main__":
    unittest.main()

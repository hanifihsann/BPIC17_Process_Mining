import unittest
from datetime import datetime, timezone

import pandas as pd
from pm4py.objects.log.obj import Event, EventLog, Trace

from modules.data_loader import get_case_trace, validate_log


def make_log(timestamp, case_id="Case_1"):
    event = Event({"concept:name": "A", "time:timestamp": timestamp})
    return EventLog([Trace([event], attributes={"concept:name": case_id})])


class ValidateLogTests(unittest.TestCase):
    def test_valid_timestamp(self):
        result = validate_log(
            make_log(datetime(2026, 1, 1, tzinfo=timezone.utc))
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing_value_counts"]["time:timestamp"], 0)
        self.assertEqual(result["invalid_value_counts"]["time:timestamp"], 0)

    def test_invalid_timestamp_string(self):
        result = validate_log(make_log("not-a-timestamp"))
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_value_counts"]["time:timestamp"], 1)

    def test_none_timestamp(self):
        result = validate_log(make_log(None))
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_value_counts"]["time:timestamp"], 1)

    def test_nan_timestamp(self):
        result = validate_log(make_log(float("nan")))
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_value_counts"]["time:timestamp"], 1)

    def test_pandas_na_timestamp(self):
        result = validate_log(make_log(pd.NA))
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_value_counts"]["time:timestamp"], 1)

    def test_timestamp_is_not_modified(self):
        timestamp = "2026-01-01T00:00:00Z"
        log = make_log(timestamp)
        validate_log(log)
        self.assertEqual(log[0][0]["time:timestamp"], timestamp)

    def test_empty_trace_case_id(self):
        result = validate_log(make_log(datetime.now(timezone.utc), case_id=None))
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_value_counts"]["trace:concept:name"], 1)

    def test_blank_and_duplicate_case_ids_are_rejected(self):
        timestamp = datetime.now(timezone.utc)
        log = make_log(timestamp)
        log.append(make_log(timestamp)[0])
        log.append(make_log(timestamp, case_id="  ")[0])
        result = validate_log(log)
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_value_counts"]["trace:concept:name"], 1)
        self.assertEqual(result["missing_value_counts"]["trace:concept:name"], 1)

    def test_dataframe_required_values(self):
        dataframe = pd.DataFrame(
            {
                "case:concept:name": ["Case_1", None],
                "concept:name": ["A", None],
                "time:timestamp": ["2026-01-01T00:00:00Z", None],
            }
        )
        result = validate_log(dataframe)
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_value_counts"]["trace:concept:name"], 1)
        self.assertEqual(result["missing_value_counts"]["concept:name"], 1)
        self.assertEqual(result["missing_value_counts"]["time:timestamp"], 1)

    def test_optional_attributes(self):
        event = Event(
            {
                "concept:name": "A",
                "time:timestamp": datetime.now(timezone.utc),
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
            }
        )
        result = validate_log(
            EventLog([Trace([event], attributes={"concept:name": "Case_1"})])
        )
        self.assertTrue(result["valid"])
        self.assertEqual(
            result["optional_attributes"],
            {"lifecycle:transition": True, "org:resource": True},
        )

    def test_get_case_trace_event_log_preserves_order_and_attributes(self):
        first_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        second_timestamp = datetime(2026, 1, 2, tzinfo=timezone.utc)
        log = EventLog(
            [
                Trace(
                    [
                        Event(
                            {
                                "concept:name": "B",
                                "time:timestamp": first_timestamp,
                                "lifecycle:transition": "start",
                                "org:resource": "User_1",
                            }
                        ),
                        Event(
                            {
                                "concept:name": "A",
                                "time:timestamp": second_timestamp,
                                "lifecycle:transition": "complete",
                                "org:resource": "User_2",
                            }
                        ),
                    ],
                    attributes={"concept:name": "Case_1"},
                )
            ]
        )
        original_order = [event["concept:name"] for event in log[0]]

        result = get_case_trace(log, "Case_1")

        self.assertEqual(
            result,
            [
                {
                    "activity": "B",
                    "timestamp": first_timestamp,
                    "lifecycle": "start",
                    "resource": "User_1",
                },
                {
                    "activity": "A",
                    "timestamp": second_timestamp,
                    "lifecycle": "complete",
                    "resource": "User_2",
                },
            ],
        )
        self.assertEqual(
            [event["concept:name"] for event in log[0]], original_order
        )

    def test_get_case_trace_event_log_returns_none_for_missing_optional_attributes(self):
        log = make_log(datetime(2026, 1, 1, tzinfo=timezone.utc))

        result = get_case_trace(log, "Case_1")

        self.assertEqual(result[0]["lifecycle"], None)
        self.assertEqual(result[0]["resource"], None)

    def test_get_case_trace_returns_empty_for_unknown_case(self):
        result = get_case_trace(make_log(datetime(2026, 1, 1, tzinfo=timezone.utc)), "Unknown")
        self.assertEqual(result, [])

    def test_get_case_trace_dataframe_preserves_row_order(self):
        dataframe = pd.DataFrame(
            {
                "case:concept:name": ["Case_1", "Case_2", "Case_1"],
                "concept:name": ["B", "X", "A"],
                "time:timestamp": ["t1", "t2", "t3"],
                "lifecycle:transition": ["start", "complete", "complete"],
                "org:resource": ["User_1", "User_9", "User_2"],
            }
        )

        result = get_case_trace(dataframe, "Case_1")

        self.assertEqual([row["activity"] for row in result], ["B", "A"])
        self.assertEqual([row["timestamp"] for row in result], ["t1", "t3"])
        self.assertEqual([row["resource"] for row in result], ["User_1", "User_2"])

    def test_get_case_trace_dataframe_optional_columns_default_to_none(self):
        dataframe = pd.DataFrame(
            {
                "case:concept:name": ["Case_1"],
                "concept:name": ["A"],
                "time:timestamp": ["t1"],
            }
        )

        result = get_case_trace(dataframe, "Case_1")

        self.assertEqual(result[0]["lifecycle"], None)
        self.assertEqual(result[0]["resource"], None)


if __name__ == "__main__":
    unittest.main()

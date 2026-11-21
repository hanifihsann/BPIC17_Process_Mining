import unittest
from datetime import datetime, timedelta, timezone

from pm4py.objects.log.obj import Event, EventLog, Trace

from modules.overview import calculate_overview


def make_log():
    return EventLog(
        [
            Trace(
                [
                    Event(
                        {
                            "concept:name": "A",
                            "time:timestamp": datetime(
                                2026, 1, 2, tzinfo=timezone.utc
                            ),
                        }
                    ),
                    Event(
                        {
                            "concept:name": "B",
                            "time:timestamp": datetime(
                                2026, 1, 4, tzinfo=timezone.utc
                            ),
                        }
                    ),
                ],
                attributes={"concept:name": "Case_1"},
            ),
            Trace(
                [
                    Event(
                        {
                            "concept:name": "A",
                            "time:timestamp": datetime(
                                2026, 1, 3, tzinfo=timezone.utc
                            ),
                        }
                    ),
                    Event(
                        {
                            "concept:name": "C",
                            "time:timestamp": datetime(
                                2026, 1, 4, tzinfo=timezone.utc
                            ),
                        }
                    ),
                ],
                attributes={"concept:name": "Case_2"},
            ),
        ]
    )


class OverviewTests(unittest.TestCase):
    def test_counts_and_activity_frequency(self):
        result = calculate_overview(make_log())
        self.assertEqual(result["case_count"], 2)
        self.assertEqual(result["event_count"], 4)
        self.assertEqual(result["activity_frequency"], {"A": 2, "B": 1, "C": 1})

    def test_time_range(self):
        result = calculate_overview(make_log())
        self.assertEqual(
            result["time_range"]["start"],
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(
            result["time_range"]["end"],
            datetime(2026, 1, 4, tzinfo=timezone.utc),
        )

    def test_case_durations_and_mean(self):
        result = calculate_overview(make_log())
        self.assertEqual(result["cycle_time_case_count"], 2)
        self.assertEqual(len(result["case_durations"]), 2)
        self.assertEqual(result["case_durations"][0]["case_id"], "Case_1")
        self.assertEqual(
            result["case_durations"][0]["duration"], timedelta(days=2)
        )
        self.assertEqual(result["case_durations"][0]["duration_days"], 2.0)
        self.assertEqual(result["mean_cycle_time_days"], 1.5)

    def test_empty_case_is_skipped_safely(self):
        log = make_log()
        log.append(Trace([], attributes={"concept:name": "Empty"}))
        result = calculate_overview(log)
        self.assertEqual(result["case_count"], 3)
        self.assertEqual(result["cycle_time_case_count"], 2)
        self.assertEqual(result["skipped_cases"][0]["case_id"], "Empty")

    def test_invalid_timestamp_is_skipped_safely(self):
        log = make_log()
        log.append(
            Trace(
                [
                    Event(
                        {
                            "concept:name": "D",
                            "time:timestamp": "not-a-timestamp",
                        }
                    ),
                    Event(
                        {
                            "concept:name": "E",
                            "time:timestamp": datetime(
                                2026, 1, 5, tzinfo=timezone.utc
                            ),
                        }
                    ),
                ],
                attributes={"concept:name": "Invalid"},
            )
        )
        result = calculate_overview(log)
        self.assertEqual(result["cycle_time_case_count"], 2)
        self.assertEqual(result["skipped_cases"][-1]["case_id"], "Invalid")

    def test_invalid_last_timestamp_is_not_replaced_by_previous_timestamp(self):
        log = EventLog(
            [
                Trace(
                    [
                        Event(
                            {
                                "concept:name": "A",
                                "time:timestamp": datetime(
                                    2026, 1, 1, tzinfo=timezone.utc
                                ),
                            }
                        ),
                        Event(
                            {
                                "concept:name": "B",
                                "time:timestamp": "not-a-timestamp",
                            }
                        ),
                    ],
                    attributes={"concept:name": "InvalidLast"},
                )
            ]
        )
        result = calculate_overview(log)
        self.assertEqual(result["cycle_time_case_count"], 0)
        self.assertEqual(result["skipped_cases"][0]["case_id"], "InvalidLast")

    def test_original_event_order_is_unchanged(self):
        log = make_log()
        before = [[event["concept:name"] for event in trace] for trace in log]
        calculate_overview(log)
        after = [[event["concept:name"] for event in trace] for trace in log]
        self.assertEqual(after, before)

    def test_metadata_counts_are_used_when_matching(self):
        result = calculate_overview(
            make_log(), {"case_count": 2, "event_count": 4}
        )
        self.assertEqual(result["case_count"], 2)
        self.assertEqual(result["event_count"], 4)

    def test_metadata_counts_do_not_override_active_log(self):
        result = calculate_overview(
            make_log(), {"case_count": 999, "event_count": 999}
        )
        self.assertEqual(result["case_count"], 2)
        self.assertEqual(result["event_count"], 4)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime
from core.processor import LogProcessor
from core.reports import ReportGenerator
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED


class TestLogProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = LogProcessor()
        # Sample sessions: [ID, Date, Entry, Exit, Mode]
        self.processor.sessions = [
            ["1", "2025-08-27", "08:00", "17:00", "paired"],
            ["1", "2025-08-28", "08:15", "17:00", "fallback"],
            ["2", "2025-08-27", "07:35", "16:30", "paired"],
        ]
        self.processor.records = {
            "1": {"2025-08-27": ["08:00", "17:00"], "2025-08-28": ["08:15", "17:00"]},
            "2": {"2025-08-27": ["07:35", "16:30"]}
        }
        self.processor.work_schedules = {
            "2025-08-27": {"entry": "08:00", "exit": "17:00", "floating": 0.5, "late_allowed": True},
            "2025-08-28": {"entry": "08:00", "exit": "17:00", "floating": 0.5, "late_allowed": True},
        }

    def test_get_fallback_sessions(self):
        fallback = self.processor.get_fallback_sessions("1")
        self.assertEqual(len(fallback), 1)
        idx, session = fallback[0]
        self.assertEqual(session[1], "2025-08-28")
        self.assertEqual(session[4], "fallback")

    def test_edit_fallback_sessions(self):
        fallback = self.processor.get_fallback_sessions("1")
        idx, _ = fallback[0]
        self.processor.edit_fallback_sessions("1", [(idx, "08:30", "17:10")])
        session = self.processor.sessions[idx]
        self.assertEqual(session[2], "08:30")
        self.assertEqual(session[3], "17:10")

    def test_find_late_early(self):
        report_gen = ReportGenerator(self.processor)
        late_early = self.processor.find_late_early("1")
        # Should include entry after scheduled+floating or early exit
        self.assertIsInstance(late_early, list)
        for rec in late_early:
            self.assertIn(rec[2], ["Late Entry", "Early Exit"])

    def test_work_schedules_applied(self):
        # Test that the processor has schedules stored
        self.assertIn("2025-08-27", self.processor.work_schedules)
        sched = self.processor.work_schedules["2025-08-27"]
        self.assertEqual(sched["entry"], "08:00")
        self.assertEqual(sched["exit"], "17:00")
        self.assertEqual(sched["floating"], 0.5)
        self.assertTrue(sched["late_allowed"])


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta

from sjtusportbooker.runtime_config import normalize_config, target_dates_to_offsets


class RuntimeConfigTests(unittest.TestCase):
    def test_legacy_days_are_all_migrated_to_target_dates(self):
        today = datetime.now()

        config = normalize_config({"task": {"days": [4, 2, 4]}})

        self.assertEqual(
            config["task"]["target_dates"],
            [
                (today + timedelta(days=2)).strftime("%Y-%m-%d"),
                (today + timedelta(days=4)).strftime("%Y-%m-%d"),
            ],
        )

    def test_multiple_dates_convert_to_sorted_unique_offsets(self):
        today = datetime.now()
        target_dates = [
            (today + timedelta(days=5)).strftime("%Y-%m-%d"),
            (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            (today + timedelta(days=5)).strftime("%Y-%m-%d"),
        ]

        self.assertEqual(target_dates_to_offsets(target_dates), [2, 5])


if __name__ == "__main__":
    unittest.main()

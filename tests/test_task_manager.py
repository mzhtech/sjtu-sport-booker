import unittest
from unittest.mock import patch

from sjtusportbooker.task_manager import TaskManager


class FakeWorkerSuccess:
    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        self.logger("Login Successfully!")

    def book(self):
        return True

    def close(self):
        return None


class FakeWorkerFailure:
    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        self.logger("Login Successfully!")

    def book(self):
        raise Exception("NoSuchElementError: missing booking slot")

    def close(self):
        return None


class FakeWorkerFalse:
    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        self.logger("Login Successfully!")

    def book(self):
        return False

    def close(self):
        return None


class FakeWorkerNoBlocks:
    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        self.logger("Login Successfully!")

    def book(self):
        self.logger("No time blocks rendered for 2026-05-05, will retry after refresh")
        return False

    def close(self):
        return None


class TaskManagerTests(unittest.TestCase):
    def base_config(self):
        return {
            "account": {"username": "alice", "password": "secret"},
            "task": {
                "venue": "霍英东体育中心",
                "venue_item": "篮球",
                "target_date": "2026-05-05",
                "times": [12],
                "headless": True,
                "pre_poll_ms": 1000,
                "post_poll_ms": 500,
            },
            "notification": {"enabled": False},
        }

    def test_successful_run_logs_login_once(self):
        manager = TaskManager()

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerSuccess):
            manager._run_task(self.base_config())

        messages = [entry["message"] for entry in manager.logs()]
        self.assertEqual(messages.count("Login Successfully!"), 1)
        self.assertEqual(manager.status()["state"], "success")

    def test_failed_run_marks_error_instead_of_stopped(self):
        manager = TaskManager()

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerFailure):
            manager._run_task(self.base_config())

        self.assertEqual(manager.status()["state"], "error")
        self.assertIn("NoSuchElementError", manager.status()["message"])

    def test_false_return_without_manual_stop_marks_error(self):
        manager = TaskManager()

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerFalse):
            manager._run_task(self.base_config())

        self.assertEqual(manager.status()["state"], "error")
        self.assertIn("未成功预约", manager.status()["message"])

    def test_false_return_with_retry_log_stays_stopped(self):
        manager = TaskManager()
        manager._stop_event.set()

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerNoBlocks):
            manager._run_task(self.base_config())

        self.assertEqual(manager.status()["state"], "stopped")


if __name__ == "__main__":
    unittest.main()

import unittest
import random
from unittest.mock import patch

from sjtusportbooker.task_manager import TaskManager, _distribute_target_dates


class FakeWorkerSuccess:
    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        self.logger("Login Successfully!")

    def book(self):
        return True

    def export_session(self):
        return {"cookies": [], "local_storage": {}, "session_storage": {}}

    def restore_session(self, session_state):
        self.logger("Authenticated session restored")

    def close(self):
        return None


class FakeWorkerFailure:
    login_calls = 0
    book_calls = 0

    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        type(self).login_calls += 1
        self.logger("Login Successfully!")

    def book(self):
        type(self).book_calls += 1
        if type(self).book_calls == 1:
            raise Exception("HTTPConnectionPool: Read timed out")
        return True

    def export_session(self):
        return {"cookies": [], "local_storage": {}, "session_storage": {}}

    def close(self):
        return None


class FakeWorkerFalse:
    login_calls = 0
    book_calls = 0

    def __init__(self, *args, **kwargs):
        self.logger = kwargs["logger"]

    def login(self):
        type(self).login_calls += 1
        self.logger("Login Successfully!")

    def book(self):
        type(self).book_calls += 1
        return type(self).book_calls > 1

    def export_session(self):
        return {"cookies": [], "local_storage": {}, "session_storage": {}}

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


class FakeWorkerConcurrentSuccess(FakeWorkerSuccess):
    instances = 0
    login_calls = 0
    restore_calls = 0
    date_assignments = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        type(self).instances += 1
        type(self).date_assignments.append(tuple(args[0]["date"]))

    def login(self):
        type(self).login_calls += 1
        super().login()

    def restore_session(self, session_state):
        type(self).restore_calls += 1
        super().restore_session(session_state)


class TaskManagerTests(unittest.TestCase):
    def base_config(self):
        return {
            "account": {"username": "alice", "password": "secret"},
            "task": {
                "venue": "霍英东体育中心",
                "venue_item": "篮球",
                "target_dates": ["2026-05-05", "2026-05-06"],
                "times": [12],
                "concurrency": 1,
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
        self.assertEqual(sum(message.endswith("Login Successfully!") for message in messages), 1)
        self.assertEqual(manager.status()["state"], "success")

    def test_configured_concurrency_starts_multiple_workers_and_notifies_once(self):
        manager = TaskManager()
        config = self.base_config()
        config["task"]["concurrency"] = 3
        config["task"]["target_dates"] = [
            "2026-05-05",
            "2026-05-06",
            "2026-05-07",
            "2026-05-08",
            "2026-05-09",
        ]
        FakeWorkerConcurrentSuccess.instances = 0
        FakeWorkerConcurrentSuccess.login_calls = 0
        FakeWorkerConcurrentSuccess.restore_calls = 0
        FakeWorkerConcurrentSuccess.date_assignments = []

        with (
            patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerConcurrentSuccess),
            patch.object(manager, "_notify_async") as notify,
        ):
            manager._run_task(config)

        self.assertEqual(FakeWorkerConcurrentSuccess.instances, 3)
        self.assertEqual(FakeWorkerConcurrentSuccess.login_calls, 1)
        self.assertEqual(FakeWorkerConcurrentSuccess.restore_calls, 2)
        assignment_sets = [set(items) for items in FakeWorkerConcurrentSuccess.date_assignments]
        self.assertEqual(sorted(len(items) for items in assignment_sets), [1, 2, 2])
        self.assertEqual(len(set().union(*assignment_sets)), 5)
        for index, assignment in enumerate(assignment_sets):
            for other in assignment_sets[index + 1:]:
                self.assertTrue(assignment.isdisjoint(other))
        self.assertEqual(manager.status()["state"], "success")
        notify.assert_called_once_with(config, True)

    def test_dates_are_randomly_distributed_without_overlap(self):
        dates = [f"2026-05-{day:02d}" for day in range(1, 8)]

        assignments = _distribute_target_dates(dates, 3, rng=random.Random(42))

        self.assertEqual(sorted(len(items) for items in assignments), [2, 2, 3])
        self.assertEqual(sorted(date for items in assignments for date in items), dates)
        for index, assignment in enumerate(assignments):
            for other in assignments[index + 1:]:
                self.assertTrue(set(assignment).isdisjoint(other))

    def test_concurrency_is_capped_by_number_of_dates(self):
        assignments = _distribute_target_dates(
            ["2026-05-05", "2026-05-06"],
            10,
            rng=random.Random(42),
        )

        self.assertEqual(len(assignments), 2)
        self.assertTrue(all(len(items) == 1 for items in assignments))

    def test_driver_timeout_restarts_full_flow_and_logs_in_again(self):
        manager = TaskManager()
        manager.retry_delay_seconds = 0
        FakeWorkerFailure.login_calls = 0
        FakeWorkerFailure.book_calls = 0

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerFailure):
            manager._run_task(self.base_config())

        messages = [entry["message"] for entry in manager.logs()]
        self.assertEqual(manager.status()["state"], "success")
        self.assertEqual(FakeWorkerFailure.login_calls, 2)
        self.assertTrue(any("Full-flow retry 1" in message for message in messages))
        self.assertTrue(any("Starting full-flow cycle 2" in message for message in messages))

    def test_early_worker_exit_restarts_full_flow(self):
        manager = TaskManager()
        manager.retry_delay_seconds = 0
        FakeWorkerFalse.login_calls = 0
        FakeWorkerFalse.book_calls = 0

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerFalse):
            manager._run_task(self.base_config())

        self.assertEqual(manager.status()["state"], "success")
        self.assertEqual(FakeWorkerFalse.login_calls, 2)

    def test_false_return_with_retry_log_stays_stopped(self):
        manager = TaskManager()
        manager._stop_event.set()

        with patch("sjtusportbooker.task_manager.SportBooker", FakeWorkerNoBlocks):
            manager._run_task(self.base_config())

        self.assertEqual(manager.status()["state"], "stopped")


if __name__ == "__main__":
    unittest.main()

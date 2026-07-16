import unittest
import threading
from unittest.mock import patch

from sjtusportbooker.sport_booker import SportBooker


class FakeElement:
    def __init__(self, children=None, click_error=None):
        self.children = children or []
        self.click_error = click_error
        self.click_count = 0

    def click(self):
        self.click_count += 1
        if self.click_error is not None:
            raise self.click_error
        return None

    def find_elements(self, by, value):
        return self.children


class SportBookerTests(unittest.TestCase):
    def create_search_worker(self, dates):
        logs = []
        worker = SportBooker.__new__(SportBooker)
        worker.date = dates
        worker.time = [12]
        worker.ordered_flag = False
        worker.stop_event = None
        worker.logger = logs.append
        worker._available_dates = lambda: set(dates)
        return worker, logs

    def test_search_time_continues_after_empty_date_and_checks_later_dates(self):
        dates = ["2026-05-05", "2026-05-06", "2026-05-07"]
        worker, logs = self.create_search_worker(dates)
        selected_dates = []
        worker._select_date = selected_dates.append
        empty_slot = FakeElement(children=[])
        worker._load_time_slots = lambda date: [] if date == dates[0] else [empty_slot] * 8

        result = worker.searchTime()

        self.assertFalse(worker.ordered_flag)
        self.assertEqual(result, "partial")
        self.assertEqual(selected_dates, dates)
        self.assertIn("No time blocks rendered for 2026-05-05; continuing with remaining dates", logs)
        self.assertIn("Completed date check: 2026-05-06", logs)
        self.assertIn("Completed date check: 2026-05-07", logs)

    def test_search_time_continues_after_one_date_selection_error(self):
        dates = ["2026-05-05", "2026-05-06", "2026-05-07"]
        worker, logs = self.create_search_worker(dates)
        selected_dates = []

        def select_date(date):
            selected_dates.append(date)
            if date == dates[1]:
                raise RuntimeError("date tab missing")

        worker._select_date = select_date
        worker._load_time_slots = lambda _: [FakeElement(children=[])] * 8

        result = worker.searchTime()

        self.assertEqual(result, "partial")
        self.assertEqual(selected_dates, dates)
        self.assertIn("Completed date check: 2026-05-07", logs)
        self.assertTrue(any("date tab missing" in message for message in logs))

    def test_search_time_marks_platform_unavailable_date_and_checks_others(self):
        dates = ["2026-05-05", "2026-05-06", "2026-05-07"]
        worker, logs = self.create_search_worker(dates)
        selected_dates = []
        worker._available_dates = lambda: {dates[0], dates[2]}
        worker._select_date = selected_dates.append
        worker._load_time_slots = lambda _: [FakeElement(children=[])] * 8

        result = worker.searchTime()

        self.assertEqual(result, "partial")
        self.assertEqual(selected_dates, [dates[0], dates[2]])
        self.assertTrue(any("2026-05-06 is not currently offered" in message for message in logs))
        self.assertIn("Completed date check: 2026-05-07", logs)

    def test_search_time_reports_checked_when_every_date_was_scanned(self):
        dates = ["2026-05-05", "2026-05-06"]
        worker, logs = self.create_search_worker(dates)
        worker._select_date = lambda _: None
        worker._load_time_slots = lambda _: [FakeElement(children=[])] * 8

        result = worker.searchTime()

        self.assertEqual(result, "checked")
        self.assertIn(
            "Date scan summary | checked: 2026-05-05, 2026-05-06 | retry: none",
            logs,
        )

    def test_shared_booking_lock_allows_only_one_concurrent_confirmation(self):
        booking_lock = threading.Lock()
        stop_event = threading.Event()
        success_event = threading.Event()
        confirmations = []
        workers = []

        for worker_id in range(2):
            worker, _ = self.create_search_worker(["2026-05-05"])
            worker._select_date = lambda _: None
            worker._load_time_slots = lambda _: [FakeElement(children=[])] * 5 + [
                FakeElement(children=[FakeElement()])
            ]
            worker.stop_event = stop_event
            worker.booking_lock = booking_lock
            worker.success_event = success_event
            worker.click_element = lambda *_: None
            worker.confirmOrder = lambda worker_id=worker_id: confirmations.append(worker_id)
            workers.append(worker)

        results = []

        def scan(worker):
            try:
                results.append(worker.searchTime())
            except InterruptedError:
                results.append("stopped")

        threads = [threading.Thread(target=scan, args=(worker,)) for worker in workers]
        with patch("sjtusportbooker.sport_booker.sleep", lambda _: None):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(len(confirmations), 1)
        self.assertEqual(results.count("ordered"), 1)
        self.assertTrue(success_event.is_set())

    def test_book_uses_light_retry_before_full_refresh(self):
        logs = []
        refresh_calls = []
        search_time_results = iter(["empty_blocks", "empty_blocks", "checked"])
        worker = SportBooker.__new__(SportBooker)
        worker.venue = "霍英东体育中心"
        worker.venueItem = "篮球"
        worker.date = ["2026-05-05"]
        worker.time = [12]
        worker.tryTimes = 0
        worker.ordered_flag = False
        worker.stop_event = None
        worker.poll_interval = 0
        worker.status_callback = None
        worker.logger = logs.append
        worker.driver = type("Driver", (), {"refresh": lambda self: refresh_calls.append("refresh")})()
        worker.searchVenue = lambda: None
        worker.searchVenueItem = lambda: None

        def fake_search_time():
            result = next(search_time_results)
            if result == "checked":
                worker.ordered_flag = True
            return result

        worker.searchTime = fake_search_time

        with patch("sjtusportbooker.sport_booker.sleep", lambda _: None):
            result = worker.book()

        self.assertTrue(result)
        self.assertEqual(refresh_calls, [])

    def test_book_full_refreshes_after_reaching_empty_block_limit(self):
        refresh_calls = []
        worker = SportBooker.__new__(SportBooker)
        worker.venue = "霍英东体育中心"
        worker.venueItem = "篮球"
        worker.date = ["2026-05-05"]
        worker.time = [12]
        worker.tryTimes = 0
        worker.ordered_flag = False
        worker.stop_event = None
        worker.poll_interval = 0
        worker.status_callback = None
        worker.logger = lambda *_: None
        worker.driver = type("Driver", (), {"refresh": lambda self: refresh_calls.append("refresh")})()
        worker.searchVenue = lambda: None
        worker.searchVenueItem = lambda: None
        calls = {"count": 0}

        def fake_search_time():
            calls["count"] += 1
            if calls["count"] <= 3:
                return "empty_blocks"
            worker.ordered_flag = True
            return "checked"

        worker.searchTime = fake_search_time

        with patch("sjtusportbooker.sport_booker.sleep", lambda _: None):
            result = worker.book()

        self.assertTrue(result)
        self.assertEqual(refresh_calls, ["refresh"])

    def test_click_element_falls_back_to_javascript_click(self):
        logs = []
        executed_scripts = []
        seat = FakeElement(click_error=Exception("ElementClickInterceptedError"))
        worker = SportBooker.__new__(SportBooker)
        worker.logger = logs.append
        worker.driver = type(
            "Driver",
            (),
            {"execute_script": lambda self, script, element: executed_scripts.append((script, element))},
        )()

        worker.click_element(seat, "seat selection")

        self.assertEqual(seat.click_count, 1)
        self.assertEqual(len(executed_scripts), 1)
        self.assertIn("Falling back to JavaScript click for seat selection", logs)

    def test_click_element_falls_back_on_not_interactable_error(self):
        logs = []
        executed_scripts = []
        button = FakeElement(click_error=Exception("ElementNotInteractableError"))
        worker = SportBooker.__new__(SportBooker)
        worker.logger = logs.append
        worker.driver = type(
            "Driver",
            (),
            {"execute_script": lambda self, script, element: executed_scripts.append((script, element))},
        )()

        worker.click_element(button, "confirm order button")

        self.assertEqual(button.click_count, 1)
        self.assertEqual(len(executed_scripts), 1)
        self.assertIn("Falling back to JavaScript click for confirm order button", logs)

    def test_book_continues_polling_after_search_error(self):
        refresh_calls = []
        logs = []
        worker = SportBooker.__new__(SportBooker)
        worker.venue = "霍英东体育中心"
        worker.venueItem = "篮球"
        worker.date = ["2026-05-05"]
        worker.time = [7, 18, 29]
        worker.tryTimes = 0
        worker.ordered_flag = False
        worker.stop_event = None
        worker.poll_interval = 0
        worker.status_callback = None
        worker.logger = logs.append
        worker.driver = type("Driver", (), {"refresh": lambda self: refresh_calls.append("refresh")})()
        worker.searchVenue = lambda: None
        worker.searchVenueItem = lambda: None
        calls = {"count": 0}

        def fake_search_time():
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("searchTime[2026-05-05 29:00] failed: time slot index 22 out of range")
            worker.ordered_flag = True
            return "ordered"

        worker.searchTime = fake_search_time

        with patch("sjtusportbooker.sport_booker.sleep", lambda _: None):
            result = worker.book()

        self.assertTrue(result)
        self.assertEqual(refresh_calls, ["refresh"])
        self.assertIn("[Book ERROR]: searchTime[2026-05-05 29:00] failed: time slot index 22 out of range", logs)
        self.assertEqual(worker.tryTimes, 2)


if __name__ == "__main__":
    unittest.main()

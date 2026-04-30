import unittest
from unittest.mock import patch

from sjtu-sport-booker.sjtu-sport-booker import sjtu-sport-booker


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


class FakeWait:
    def __init__(self, driver, timeout):
        self.responses = driver["_responses"]

    def until(self, condition):
        return self.responses.pop(0)


class sjtu-sport-bookerTests(unittest.TestCase):
    def test_search_time_retries_when_no_blocks_rendered(self):
        logs = []
        worker = sjtu-sport-booker.__new__(sjtu-sport-booker)
        worker.date = ["2026-05-05"]
        worker.time = [12]
        worker.ordered_flag = False
        worker.stop_event = None
        worker.driver = {"_responses": [FakeElement(), FakeElement(children=[])]}
        worker.logger = logs.append

        with patch("sjtu-sport-booker.sjtu-sport-booker.WebDriverWait", FakeWait):
            result = worker.searchTime()

        self.assertFalse(worker.ordered_flag)
        self.assertEqual(result, "empty_blocks")
        self.assertIn("No time blocks rendered for 2026-05-05, will retry after refresh", logs)

    def test_book_uses_light_retry_before_full_refresh(self):
        logs = []
        refresh_calls = []
        search_time_results = iter(["empty_blocks", "empty_blocks", "checked"])
        worker = sjtu-sport-booker.__new__(sjtu-sport-booker)
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

        with patch("sjtu-sport-booker.sjtu-sport-booker.sleep", lambda _: None):
            result = worker.book()

        self.assertTrue(result)
        self.assertEqual(refresh_calls, [])

    def test_book_full_refreshes_after_reaching_empty_block_limit(self):
        refresh_calls = []
        worker = sjtu-sport-booker.__new__(sjtu-sport-booker)
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

        with patch("sjtu-sport-booker.sjtu-sport-booker.sleep", lambda _: None):
            result = worker.book()

        self.assertTrue(result)
        self.assertEqual(refresh_calls, ["refresh"])

    def test_click_element_falls_back_to_javascript_click(self):
        logs = []
        executed_scripts = []
        seat = FakeElement(click_error=Exception("ElementClickInterceptedError"))
        worker = sjtu-sport-booker.__new__(sjtu-sport-booker)
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
        worker = sjtu-sport-booker.__new__(sjtu-sport-booker)
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
        worker = sjtu-sport-booker.__new__(sjtu-sport-booker)
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

        with patch("sjtu-sport-booker.sjtu-sport-booker.sleep", lambda _: None):
            result = worker.book()

        self.assertTrue(result)
        self.assertEqual(refresh_calls, ["refresh"])
        self.assertIn("[Book ERROR]: searchTime[2026-05-05 29:00] failed: time slot index 22 out of range", logs)
        self.assertEqual(worker.tryTimes, 2)


if __name__ == "__main__":
    unittest.main()
